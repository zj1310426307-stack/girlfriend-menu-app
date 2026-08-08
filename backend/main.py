from contextlib import asynccontextmanager
import asyncio
import hashlib
import os
from pathlib import Path
import secrets

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import Base, SessionLocal, engine, ensure_compatible_schema, get_db
from realtime import dice_room_manager, order_event_hub
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
    ensure_compatible_schema()
    with SessionLocal() as db:
        seed_dishes(db)
    yield


app = FastAPI(title="女朋友专属点菜小程序 API", version="1.1.0", lifespan=lifespan)


def get_frontend_origins():
    # The product UI is now WeChat-only. CORS is kept optional for API
    # diagnostics or a future approved browser client, but has no default web UI.
    raw_urls = os.getenv("FRONTEND_URL", "")
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


def get_admin_invite_code():
    return os.getenv("ADMIN_INVITE_CODE", "love2026")


def get_admin_token():
    secret = os.getenv("ADMIN_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_SECRET",
        )
    value = f"{get_admin_password()}:{get_admin_invite_code()}:{secret}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def verify_admin_token(authorization: str | None = Header(default=None)):
    expected = f"Bearer {get_admin_token()}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理登录已失效，请重新登录",
        )


def is_admin_token(token: str | None):
    return bool(token) and secrets.compare_digest(token, get_admin_token())


def get_customer_id(x_customer_id: str | None = Header(default=None, alias="X-Customer-Id")):
    """Read the current minimal-version device identity from a request header."""
    value = (x_customer_id or "").strip()
    if not value or len(value) > 100:
        raise HTTPException(status_code=400, detail="缺少有效的 customer_id")
    return value


@app.get("/")
def root():
    return {"message": "女朋友专属点菜小程序 API 正常运行"}


@app.get("/api/health", include_in_schema=False)
def health_check():
    """Lightweight liveness endpoint for Render/Railway monitoring."""
    return {"status": "ok", "service": "girlfriend-menu-api"}


@app.get("/api/ready", include_in_schema=False)
def readiness_check(db: Session = Depends(get_db)):
    """Readiness also verifies that the configured database is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库暂时不可用",
        ) from error
    return {"status": "ready", "database": engine.dialect.name}


@app.post("/api/admin/login", response_model=schemas.AdminLoginOut)
def admin_login(data: schemas.AdminLogin):
    if not secrets.compare_digest(data.password, get_admin_password()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理密码错误",
        )
    if not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邀请码错误",
        )
    return {"token": get_admin_token()}


@app.websocket("/ws/admin/orders")
async def admin_order_events(websocket: WebSocket):
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=8)
        if auth_message.get("type") != "auth" or not is_admin_token(auth_message.get("token")):
            await websocket.send_json({"type": "error", "message": "管理登录已失效"})
            await websocket.close(code=4401)
            return
        await order_event_hub.add(websocket)
        await websocket.send_json({"type": "ready"})
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await order_event_hub.remove(websocket)


@app.post("/api/games/dice/rooms", response_model=schemas.DiceRoomOut)
async def create_dice_room(data: schemas.DiceRoomCreate):
    if not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return {"room_code": await dice_room_manager.create_room()}


@app.websocket("/ws/games/dice/{room_code}")
async def dice_room_socket(websocket: WebSocket, room_code: str):
    await websocket.accept()
    player_id = None
    normalized_room_code = room_code.strip().upper()
    try:
        join_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        if join_message.get("type") != "join":
            await websocket.send_json({"type": "error", "message": "请先加入房间"})
            await websocket.close(code=4400)
            return
        if not secrets.compare_digest(
            str(join_message.get("invite_code") or ""),
            get_admin_invite_code(),
        ):
            await websocket.send_json({"type": "error", "message": "邀请码错误"})
            await websocket.close(code=4401)
            return
        player_id = str(join_message.get("player_id") or "")[:100]
        player_name = str(join_message.get("name") or "玩家")[:20]
        if not player_id:
            await websocket.send_json({"type": "error", "message": "玩家标识不能为空"})
            await websocket.close(code=4400)
            return
        joined, message = await dice_room_manager.join(
            normalized_room_code,
            player_id,
            player_name,
            websocket,
        )
        if not joined:
            await websocket.send_json({"type": "error", "message": message})
            await websocket.close(code=4404)
            return
        while True:
            action = await websocket.receive_json()
            error = await dice_room_manager.handle(normalized_room_code, player_id, action)
            if error:
                await websocket.send_json({"type": "error", "message": error})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if player_id:
            await dice_room_manager.leave(normalized_room_code, player_id, websocket)


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
async def submit_order(data: schemas.OrderCreate, db: Session = Depends(get_db)):
    order = crud.create_order(db, data)
    await order_event_hub.broadcast("order_created", order.id)
    return order


@app.post("/api/orders/repeat/{order_id}", response_model=schemas.OrderRepeatDraft)
def repeat_order(
    order_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return crud.repeat_order_draft(db, order_id, customer_id)


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
async def change_order_status(
    order_id: int,
    data: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    order = crud.update_order_status(db, order_id, data.status)
    await order_event_hub.broadcast("order_status_changed", order.id)
    return order


@app.post(
    "/api/orders/{order_id}/review",
    response_model=schemas.ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_order_review(
    order_id: int,
    data: schemas.ReviewCreate,
    db: Session = Depends(get_db),
):
    review = crud.create_review(db, order_id, data)
    await order_event_hub.broadcast("order_reviewed", order_id)
    return review


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
