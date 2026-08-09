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
import love_score
import models
import schemas
from database import Base, SessionLocal, engine, ensure_compatible_schema, get_db
from realtime import game_room_manager, order_event_hub
from seed import seed_dishes, seed_games
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
        seed_games(db)
    yield


app = FastAPI(title="情侣智能厨房管家 API", version="2.2.0", lifespan=lifespan)


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


@app.get("/api/games", response_model=list[schemas.GameOut])
def games(db: Session = Depends(get_db)):
    return crud.list_games(db)


@app.post(
    "/api/games/rooms",
    response_model=schemas.GameRoomOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_game_room(data: schemas.GameRoomCreate, db: Session = Depends(get_db)):
    if not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    room = crud.create_game_room(db, data.game_type, data.creator)
    await game_room_manager.ensure_room(room.room_code, room.game_type, room.max_players)
    return room


@app.get("/api/games/rooms/{room_code}", response_model=schemas.GameRoomOut)
def game_room_detail(room_code: str, db: Session = Depends(get_db)):
    return crud.get_game_room(db, room_code)


@app.post("/api/games/dice/rooms", response_model=schemas.DiceRoomOut)
async def create_dice_room(data: schemas.DiceRoomCreate, db: Session = Depends(get_db)):
    """Compatibility endpoint for already uploaded 1.x clients."""
    if not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    room = crud.create_game_room(db, "dice", "legacy_client")
    await game_room_manager.ensure_room(room.room_code, room.game_type, room.max_players)
    return {"room_code": room.room_code}


async def _send_game_error(websocket: WebSocket, message: str, game_type: str, protocol: str):
    if protocol == "legacy":
        await websocket.send_json({"type": "error", "message": message})
    else:
        await websocket.send_json({"type": "error", "game": game_type, "message": message})


def _sync_game_room_status(room_code: str, room_status: str, allow_restart: bool = False):
    with SessionLocal() as db:
        room = crud.get_game_room(db, room_code)
        if room.status == "finished" and room_status != "finished" and not allow_restart:
            return
        crud.update_game_room_status(db, room_code, room_status)


async def _game_room_socket(
    websocket: WebSocket,
    room_code: str,
    protocol: str,
    forced_game_type: str | None = None,
):
    await websocket.accept()
    player_id = None
    normalized_room_code = room_code.strip().upper()
    game_type = forced_game_type or "unknown"
    try:
        try:
            with SessionLocal() as db:
                room_record = crud.get_game_room(db, normalized_room_code)
                game_type = room_record.game_type
                if room_record.status == "finished":
                    await _send_game_error(websocket, "房间已经结束", game_type, protocol)
                    await websocket.close(code=4404)
                    return
                if forced_game_type and forced_game_type != game_type:
                    await _send_game_error(websocket, "游戏类型与房间不匹配", game_type, protocol)
                    await websocket.close(code=4400)
                    return
                await game_room_manager.ensure_room(
                    normalized_room_code,
                    room_record.game_type,
                    room_record.max_players,
                )
        except HTTPException as error:
            await _send_game_error(websocket, str(error.detail), game_type, protocol)
            await websocket.close(code=4404)
            return

        join_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        join_data = (
            join_message.get("data")
            if isinstance(join_message.get("data"), dict)
            else join_message
        )
        requested_game = join_message.get("game") or forced_game_type or game_type
        if join_message.get("type") != "join":
            await _send_game_error(websocket, "请先加入房间", game_type, protocol)
            await websocket.close(code=4400)
            return
        if requested_game != game_type:
            await _send_game_error(websocket, "游戏类型与房间不匹配", game_type, protocol)
            await websocket.close(code=4400)
            return
        if not secrets.compare_digest(
            str(join_data.get("invite_code") or ""),
            get_admin_invite_code(),
        ):
            await _send_game_error(websocket, "邀请码错误", game_type, protocol)
            await websocket.close(code=4401)
            return
        player_id = str(join_data.get("player_id") or "")[:100]
        player_name = str(join_data.get("name") or "玩家")[:20]
        if not player_id:
            await _send_game_error(websocket, "玩家标识不能为空", game_type, protocol)
            await websocket.close(code=4400)
            return
        joined, message = await game_room_manager.join(
            normalized_room_code,
            player_id,
            player_name,
            websocket,
            protocol=protocol,
            game_type=game_type,
        )
        if not joined:
            await _send_game_error(websocket, message, game_type, protocol)
            await websocket.close(code=4404)
            return
        _sync_game_room_status(
            normalized_room_code,
            await game_room_manager.room_status(normalized_room_code),
        )
        while True:
            action = await websocket.receive_json()
            if action.get("type") == "ping":
                pong = {"type": "pong"}
                if protocol != "legacy":
                    pong.update(game=game_type, data={})
                await websocket.send_json(pong)
                continue
            error = await game_room_manager.handle(normalized_room_code, player_id, action)
            if error:
                await _send_game_error(websocket, error, game_type, protocol)
                continue
            _sync_game_room_status(
                normalized_room_code,
                await game_room_manager.room_status(normalized_room_code),
                allow_restart=action.get("type") == "rematch",
            )
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if player_id:
            await game_room_manager.leave(normalized_room_code, player_id, websocket)
            try:
                _sync_game_room_status(
                    normalized_room_code,
                    await game_room_manager.room_status(normalized_room_code),
                )
            except HTTPException:
                pass


@app.websocket("/ws/game/{room_code}")
async def unified_game_room_socket(websocket: WebSocket, room_code: str):
    await _game_room_socket(websocket, room_code, protocol="v2")


@app.websocket("/ws/games/dice/{room_code}")
async def dice_room_socket(websocket: WebSocket, room_code: str):
    await _game_room_socket(
        websocket,
        room_code,
        protocol="legacy",
        forced_game_type="dice",
    )


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


@app.get("/api/favorites", response_model=list[schemas.DishOut])
def favorite_dishes(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return crud.list_favorite_dishes(db, customer_id)


@app.post("/api/favorites/{dish_id}", response_model=schemas.DishOut)
def add_favorite(
    dish_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return crud.add_favorite_dish(db, customer_id, dish_id)


@app.delete("/api/favorites/{dish_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    dish_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    crud.remove_favorite_dish(db, customer_id, dish_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@app.get("/api/couple/score", response_model=schemas.LoveScoreSummary)
def couple_score(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return love_score.score_summary(db, customer_id)


@app.get("/api/couple/score/history", response_model=list[schemas.LoveScoreOut])
def couple_score_history(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return love_score.score_history(db, customer_id)


@app.post(
    "/api/couple/score/add",
    response_model=schemas.LoveScoreOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_token)],
)
def add_couple_score(
    data: schemas.LoveScoreCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return love_score.record_score(
        db,
        customer_id,
        data.type,
        data.score,
        data.description,
        data.related_id,
    )


@app.get(
    "/api/stats/favorite-ranking",
    response_model=list[schemas.FavoriteRankingItem],
)
def favorite_ranking(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return crud.get_favorite_ranking(db, customer_id)


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
