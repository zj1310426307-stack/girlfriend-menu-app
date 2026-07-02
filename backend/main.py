from contextlib import asynccontextmanager
import hashlib
import os
from pathlib import Path
import secrets

from fastapi import Depends, FastAPI, File, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import Base, SessionLocal, engine, ensure_order_customer_id_column, get_db
from seed import seed_dishes
from storage import UPLOAD_DIR, ensure_upload_directory, save_image


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ensure_upload_directory()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_upload_directory()
    Base.metadata.create_all(bind=engine)
    ensure_order_customer_id_column()
    with SessionLocal() as db:
        seed_dishes(db)
    yield


app = FastAPI(title="女朋友专属点菜小程序 API", version="1.0.0", lifespan=lifespan)


def get_frontend_origins():
    raw_urls = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [url.strip().rstrip("/") for url in raw_urls.split(",") if url.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def get_admin_password():
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_PASSWORD",
        )
    return password


def get_admin_token():
    secret = os.getenv("ADMIN_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_SECRET",
        )
    value = f"{get_admin_password()}:{secret}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def verify_admin_token(authorization: str | None = Header(default=None)):
    expected = f"Bearer {get_admin_token()}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理登录已失效，请重新登录",
        )


@app.get("/")
def root():
    return {"message": "女朋友专属点菜小程序 API 正常运行"}


@app.post("/api/admin/login", response_model=schemas.AdminLoginOut)
def admin_login(data: schemas.AdminLogin):
    if not secrets.compare_digest(data.password, get_admin_password()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理密码错误",
        )
    return {"token": get_admin_token()}


@app.post("/api/upload/image", dependencies=[Depends(verify_admin_token)])
async def upload_image(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()
    if (
        extension not in ALLOWED_IMAGE_EXTENSIONS
        or file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 jpg、jpeg、png、webp 图片",
        )

    content = await file.read(MAX_IMAGE_SIZE + 1)
    await file.close()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="图片大小不能超过 5MB",
        )

    try:
        image_url = save_image(content, extension)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        )
    return {"image_url": image_url}


@app.get("/api/dishes", response_model=list[schemas.DishOut])
def dishes(category: str | None = None, db: Session = Depends(get_db)):
    return crud.list_dishes(db, category)


@app.get("/api/dishes/{dish_id}", response_model=schemas.DishOut)
def dish_detail(dish_id: int, db: Session = Depends(get_db)):
    return crud.get_dish(db, dish_id)


@app.post(
    "/api/dishes",
    response_model=schemas.DishOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_token)],
)
def add_dish(data: schemas.DishCreate, db: Session = Depends(get_db)):
    return crud.create_dish(db, data)


@app.put(
    "/api/dishes/{dish_id}",
    response_model=schemas.DishOut,
    dependencies=[Depends(verify_admin_token)],
)
def edit_dish(dish_id: int, data: schemas.DishUpdate, db: Session = Depends(get_db)):
    return crud.update_dish(db, dish_id, data)


@app.delete(
    "/api/dishes/{dish_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_admin_token)],
)
def remove_dish(dish_id: int, db: Session = Depends(get_db)):
    crud.delete_dish(db, dish_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/orders", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def submit_order(data: schemas.OrderCreate, db: Session = Depends(get_db)):
    return crud.create_order(db, data)


@app.get(
    "/api/orders",
    response_model=list[schemas.OrderOut],
    dependencies=[Depends(verify_admin_token)],
)
def orders(db: Session = Depends(get_db)):
    return crud.list_orders(db)


@app.get("/api/orders/my/{customer_id}", response_model=list[schemas.OrderOut])
def my_orders(customer_id: str, db: Session = Depends(get_db)):
    return crud.list_customer_orders(db, customer_id)


@app.get("/api/orders/{order_id}", response_model=schemas.OrderOut)
def order_detail(order_id: int, db: Session = Depends(get_db)):
    return crud.get_order(db, order_id)


@app.patch(
    "/api/orders/{order_id}/status",
    response_model=schemas.OrderOut,
    dependencies=[Depends(verify_admin_token)],
)
def change_order_status(
    order_id: int,
    data: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    return crud.update_order_status(db, order_id, data.status)


@app.post(
    "/api/orders/{order_id}/review",
    response_model=schemas.ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def add_order_review(
    order_id: int,
    data: schemas.ReviewCreate,
    db: Session = Depends(get_db),
):
    return crud.create_review(db, order_id, data)


@app.get("/api/orders/{order_id}/review", response_model=schemas.ReviewOut)
def order_review(order_id: int, db: Session = Depends(get_db)):
    return crud.get_review(db, order_id)


@app.get(
    "/api/stats/summary",
    response_model=schemas.StatsSummary,
    dependencies=[Depends(verify_admin_token)],
)
def stats_summary(db: Session = Depends(get_db)):
    return crud.get_stats_summary(db)


@app.get(
    "/api/stats/dishes",
    response_model=list[schemas.DishStats],
    dependencies=[Depends(verify_admin_token)],
)
def stats_dishes(db: Session = Depends(get_db)):
    return crud.get_dish_stats(db)


@app.get(
    "/api/stats/recent",
    response_model=list[schemas.OrderOut],
    dependencies=[Depends(verify_admin_token)],
)
def stats_recent(db: Session = Depends(get_db)):
    return crud.get_recent_orders(db)
