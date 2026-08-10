from contextlib import asynccontextmanager, suppress
import asyncio
import logging
import os
from pathlib import Path
import secrets
import time
import uuid

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
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
import achievement_service
import animal_service
import chess_service
import flight_service
import game_data_service
import landlord_service
import love_score
import models
import schemas
import task_service
import couple_profile_service
import game_recovery_service
import notification_service
import system_stats_service
import user_service
import customer_service
from auth import issue_admin_token, verify_admin_token_value
from core.cache import state_cache
from core.rate_limit import RateLimitExceeded, rate_limiter
from database import Base, SessionLocal, engine, ensure_compatible_schema, get_db
from game_rewards import settle_game_rewards
from realtime import game_room_manager, order_event_hub
from seed import seed_achievements, seed_dishes, seed_game_events, seed_games
from storage import UPLOAD_DIR, ensure_upload_directory, save_image, storage_readiness


logger = logging.getLogger(__name__)


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ensure_upload_directory()


async def _maintenance_loop():
    """Generate durable reminders periodically; page reads remain a safe fallback."""
    while True:
        await asyncio.sleep(6 * 60 * 60)
        try:
            with SessionLocal() as db:
                customer_codes = [
                    item[0]
                    for item in db.query(models.User.user_code)
                    .filter(models.User.role == "CUSTOMER")
                    .all()
                ]
                for code in customer_codes:
                    notification_service.generate_anniversary_reminders(db, code)
        except Exception:
            logger.exception("scheduled reminder maintenance failed")


async def _game_cleanup_loop():
    """Expire inactive game sessions without deleting durable history."""
    while True:
        await asyncio.sleep(60)
        try:
            with SessionLocal() as db:
                expired_codes = crud.expire_stale_game_rooms(db)
            removed = await game_room_manager.cleanup_expired(expired_codes)
            if removed:
                logger.info("expired_game_rooms count=%s", len(removed))
        except Exception:
            logger.exception("game room cleanup failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_upload_directory()
    # Production startup runs ``alembic upgrade head`` before Uvicorn.  The
    # compatibility path is retained only for local SQLite/test convenience.
    if os.getenv("APP_ENV", "development").lower() != "production":
        Base.metadata.create_all(bind=engine)
        ensure_compatible_schema()
    with SessionLocal() as db:
        seed_dishes(db)
        seed_games(db)
        seed_game_events(db)
        seed_achievements(db)
        game_data_service.ensure_ai_catalog(db)
        user_service.seed_system_users(db)
    tasks = [
        asyncio.create_task(_maintenance_loop()),
        asyncio.create_task(_game_cleanup_loop()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="情侣智能厨房管家 API", version="2.9.1", lifespan=lifespan)


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


@app.middleware("http")
async def request_log(request: Request, call_next):
    """Emit one privacy-safe structured line for each API request."""
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    started = time.perf_counter()
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > 6 * 1024 * 1024:
        return Response(status_code=413, content="Request body is too large")
    protected_scope = None
    if request.url.path == "/api/upload/image":
        protected_scope = ("upload", 12, 3600)
    elif request.method == "POST" and request.url.path.startswith("/api/games/") and any(
        marker in request.url.path for marker in ("/rooms", "/create", "/join")
    ):
        protected_scope = ("game-room", 30, 300)
    if protected_scope:
        try:
            client = request.client.host if request.client else "unknown"
            rate_limiter.check(f"{protected_scope[0]}:{client}", protected_scope[1], protected_scope[2])
        except RateLimitExceeded:
            return Response(status_code=429, content="Too many requests")
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    duration = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Request-Id"] = request_id
    logger.info("request id=%s method=%s path=%s status=%s duration_ms=%s", request_id, request.method, request.url.path, response.status_code, duration)
    return response


def get_admin_password():
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_PASSWORD",
        )
    return password


def get_admin_invite_code():
    invite_code = os.getenv("ADMIN_INVITE_CODE")
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_INVITE_CODE",
        )
    return invite_code


def verify_admin_token(authorization: str | None = Header(default=None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    if not verify_admin_token_value(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理登录已失效，请重新登录",
        )


def is_admin_token(token: str | None):
    return verify_admin_token_value(token)


def _allow_legacy_customer_header() -> bool:
    return os.getenv("ALLOW_LEGACY_CUSTOMER_HEADER", "false").lower() in {"1", "true", "yes"}


def _bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return None


def get_optional_customer_id(
    authorization: str | None = Header(default=None),
    x_customer_id: str | None = Header(default=None, alias="X-Customer-Id"),
    db: Session = Depends(get_db),
):
    token = _bearer_token(authorization)
    if token:
        customer = customer_service.authenticate(db, token)
        user_service.ensure_user(db, customer.id, customer.display_name)
        state_cache.touch_presence(customer.id)
        return customer.id
    if _allow_legacy_customer_header() and x_customer_id:
        value = x_customer_id.strip()[:100]
        if value:
            logger.warning("deprecated_customer_header path=unknown")
            user_service.ensure_user(db, value)
            return value
    return None


def get_customer_id(
    customer_id: str | None = Depends(get_optional_customer_id),
):
    """Return the server-authenticated device identity, never a client-selected id."""
    if not customer_id:
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    return customer_id


def enforce_rate_limit(request: Request, scope: str, limit: int, window_seconds: int):
    client = request.client.host if request.client else "unknown"
    try:
        rate_limiter.check(f"{scope}:{client}", limit, window_seconds)
    except RateLimitExceeded as error:
        raise HTTPException(status_code=429, detail="操作太频繁，请稍后再试") from error


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
    storage = storage_readiness()
    return {
        "status": "ready" if storage["status"] == "ready" else "release-blocked",
        "database": engine.dialect.name,
        "redis": "ready" if state_cache.enabled else "optional-disabled",
        "storage": storage,
    }


@app.post("/api/customers/session", response_model=schemas.CustomerSessionOut)
def create_customer_session(
    data: schemas.CustomerSessionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, "customer-session", 8, 300)
    return customer_service.create_session(db, data.invite_code, data.display_name)


@app.post("/api/customers/claim-legacy", response_model=schemas.CustomerSessionOut)
def claim_legacy_customer(
    data: schemas.CustomerLegacyClaim,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, "customer-claim", 5, 600)
    return customer_service.claim_legacy(
        db, data.invite_code, data.legacy_customer_id, data.display_name
    )


@app.post("/api/customers/refresh", response_model=schemas.CustomerSessionOut)
def refresh_customer_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    customer = customer_service.authenticate(db, _bearer_token(authorization))
    return customer_service.refresh_session(db, customer)


@app.post("/api/admin/login", response_model=schemas.AdminLoginOut)
def admin_login(data: schemas.AdminLogin, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "admin-login", 60, 300)
    if not secrets.compare_digest(data.password, get_admin_password()):
        time.sleep(0.35)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理密码错误",
        )
    if not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        time.sleep(0.5)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邀请码错误",
        )
    user_service.ensure_user(db, "admin", "小厨房管理员", "ADMIN")
    token, expires_at = issue_admin_token()
    return {"token": token, "expires_at": expires_at}


@app.get("/api/users/me", response_model=schemas.UserOut)
def current_user(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the unified profile behind the legacy-compatible customer id."""
    return user_service.ensure_user(db, customer_id)


@app.put("/api/users/me", response_model=schemas.UserOut)
def update_current_user(
    data: schemas.UserUpdate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    user = user_service.ensure_user(db, customer_id)
    user.nickname = data.nickname
    user.avatar = data.avatar
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/users/presence")
def heartbeat(customer_id: str = Depends(get_customer_id)):
    """Refresh the optional Redis online marker used by private rooms."""
    state_cache.touch_presence(customer_id)
    return {"online": True, "ttl_seconds": 90}


@app.get("/api/notifications", response_model=list[schemas.NotificationOut])
def notifications(
    unread_only: bool = False,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    notification_service.generate_anniversary_reminders(db, customer_id)
    return notification_service.list_notifications(db, customer_id, unread_only)


@app.get("/api/notifications/unread-count")
def notification_unread_count(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    notification_service.generate_anniversary_reminders(db, customer_id)
    return {"count": notification_service.unread_count(db, customer_id)}


@app.patch("/api/notifications/{notification_id}/read", response_model=schemas.NotificationOut)
def read_notification(
    notification_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return notification_service.mark_read(db, customer_id, notification_id)


@app.get("/api/couple/memories", response_model=list[schemas.CoupleMemoryOut])
def couple_memories(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return couple_profile_service.list_memories(db, customer_id)


@app.post(
    "/api/couple/memories",
    response_model=schemas.CoupleMemoryOut,
    status_code=status.HTTP_201_CREATED,
)
def add_couple_memory(
    data: schemas.CoupleMemoryCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return couple_profile_service.add_memory(db, customer_id, data)


@app.delete("/api/couple/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_couple_memory(
    memory_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    couple_profile_service.delete_memory(db, customer_id, memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/couple/dates", response_model=list[schemas.CoupleDateOut])
def couple_dates(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return couple_profile_service.list_dates(db, customer_id)


@app.post(
    "/api/couple/dates",
    response_model=schemas.CoupleDateOut,
    status_code=status.HTTP_201_CREATED,
)
def add_couple_date(
    data: schemas.CoupleDateCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    item = couple_profile_service.add_date(db, customer_id, data)
    couple_profile_service.record_memory_once(
        db,
        customer_id,
        "ANNIVERSARY",
        f"记住了：{item.title}",
        "以后每个重要日子都不会悄悄错过。",
        "COUPLE_DATE",
        item.id,
        item.date,
    )
    return item


@app.delete("/api/couple/dates/{date_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_couple_date(
    date_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    couple_profile_service.delete_date(db, customer_id, date_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/couple/profile", response_model=schemas.CoupleProfileSummaryOut)
def couple_profile(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    notification_service.generate_anniversary_reminders(db, customer_id)
    return couple_profile_service.profile_summary(db, customer_id)


@app.get("/api/couple/statistics", response_model=schemas.CoupleStatisticsOut)
def couple_statistics(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return couple_profile_service.statistics(db, customer_id)


@app.get(
    "/api/admin/dashboard",
    dependencies=[Depends(verify_admin_token)],
)
def admin_dashboard(db: Session = Depends(get_db)):
    return system_stats_service.admin_dashboard(db)


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


@app.get("/api/games/records/my", response_model=list[schemas.GameRecordOut])
def my_game_records(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return crud.list_game_records(db, customer_id)


@app.get("/api/games/active", response_model=list[schemas.ActiveGameOut])
def active_games(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Discover unfinished rooms after a page or process restart."""
    return game_recovery_service.active_rooms(db, customer_id)


@app.post("/api/games/reconnect/token", response_model=schemas.ReconnectTokenOut)
def create_reconnect_token(
    data: schemas.ReconnectTokenRequest,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return game_recovery_service.issue_token(db, data.room_code, customer_id)


@app.post("/api/games/reconnect")
def reconnect_game(data: schemas.ReconnectRequest, db: Session = Depends(get_db)):
    """Resume a room from a hashed token and its authoritative durable state."""
    _, user, room = game_recovery_service.verify_token(db, data.reconnect_token)
    state_cache.touch_presence(user.user_code)
    if room.game_type == "aeroplane":
        payload = flight_service.get_state(db, room.room_code, user.user_code)
    elif room.game_type in {"landlord", "animal", "chinese_chess"}:
        payload = animal_service.get_any_state(db, room.room_code, user.user_code)
    else:
        payload = state_cache.get_game_state(room.room_code) or {
            "room_code": room.room_code,
            "game_type": room.game_type,
            "room_status": room.status,
            "reconnect_required": True,
        }
    return {"room_code": room.room_code, "game_type": room.game_type, "state": payload}


@app.get("/api/games/records/{record_id}/replay", response_model=schemas.GameReplayOut)
def game_replay(
    record_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return game_recovery_service.get_replay(db, record_id, customer_id)


@app.get(
    "/api/admin/games/stats",
    response_model=schemas.GameStatsOut,
    dependencies=[Depends(verify_admin_token)],
)
def admin_game_stats(db: Session = Depends(get_db)):
    return crud.game_stats(db)


@app.post(
    "/api/games/rooms",
    response_model=schemas.GameRoomOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_game_room(
    data: schemas.GameRoomCreate,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    # A compatibility creator value is accepted only in explicitly enabled test/dev mode.
    creator = customer_id or (data.creator if _allow_legacy_customer_header() else None)
    if not creator:
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    room = crud.create_game_room(db, data.game_type, creator)
    if data.game_type == "gomoku" and data.mode == "ai":
        crud.join_game_room(db, room.room_code, creator)
        crud.join_game_room(db, room.room_code, "ai_gomoku")
    await game_room_manager.ensure_room(room.room_code, room.game_type, room.max_players)
    await game_room_manager.restore_players(
        room.room_code,
        crud.list_game_players(db, room.room_code),
    )
    if data.game_type == "gomoku" and data.mode == "ai":
        await game_room_manager.configure_gomoku_ai(room.room_code, data.difficulty)
    db.refresh(room)
    return room


@app.get("/api/games/rooms/{room_code}", response_model=schemas.GameRoomOut)
def game_room_detail(room_code: str, db: Session = Depends(get_db)):
    return crud.get_game_room(db, room_code)


@app.post(
    "/api/games/flight/create",
    response_model=schemas.FlightStateOut,
    status_code=status.HTTP_201_CREATED,
)
def create_flight_room(
    data: schemas.FlightRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return flight_service.create_room(
        db, customer_id, data.player_name, data.mode, data.difficulty
    )


@app.post("/api/games/flight/join", response_model=schemas.FlightStateOut)
def join_flight_room(
    data: schemas.FlightRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return flight_service.join_room(db, data.room_code, customer_id, data.player_name)


@app.get("/api/games/flight/{room_code}/state", response_model=schemas.FlightStateOut)
def flight_room_state(
    room_code: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return flight_service.get_state(db, room_code, customer_id)


@app.post("/api/games/flight/action", response_model=schemas.FlightStateOut)
def flight_room_action(
    data: schemas.FlightAction,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return flight_service.perform_action(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.piece_index,
    )


@app.post(
    "/api/games/landlord/create",
    response_model=schemas.GameSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_landlord_room(
    data: schemas.LandlordRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create the first human seat in a two-human-plus-AI landlord room."""
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return landlord_service.create(
        db, customer_id, data.player_name, data.difficulty, data.mode
    )


@app.post("/api/games/landlord/join", response_model=schemas.GameSessionOut)
def join_landlord_room(
    data: schemas.LandlordRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Join the second human seat and trigger server-side dealing."""
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return landlord_service.join_room(db, data.room_code, customer_id, data.player_name)


@app.post("/api/games/landlord/action", response_model=schemas.GameSessionOut)
def landlord_action(
    data: schemas.LandlordAction,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Apply bidding, card-play, pass or chat through the authoritative engine."""
    return landlord_service.action(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.model_dump(exclude={"room_code", "action", "expected_version"}),
        data.expected_version,
    )


@app.post(
    "/api/games/animal/create",
    response_model=schemas.GameSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_animal_room(
    data: schemas.AnimalRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create couple or AI Animal Chess using the same room platform."""
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return animal_service.create(
        db,
        customer_id,
        data.player_name,
        data.mode,
        data.difficulty,
    )


@app.post("/api/games/animal/join", response_model=schemas.GameSessionOut)
def join_animal_room(
    data: schemas.AnimalRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Join the second seat in a couple Animal Chess room."""
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return animal_service.join_room(db, data.room_code, customer_id, data.player_name)


@app.post("/api/games/animal/move", response_model=schemas.GameSessionOut)
def animal_move(
    data: schemas.AnimalMove,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Apply a move, resignation or chat with optimistic version checking."""
    return animal_service.move(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.model_dump(exclude={"room_code", "action", "expected_version"}),
        data.expected_version,
    )


@app.post(
    "/api/games/chess/create",
    response_model=schemas.GameSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_chess_room(
    data: schemas.ChessRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create a couple room or an immediate server-AI Chinese-chess game."""
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return chess_service.create(db, customer_id, data.player_name, data.mode, data.difficulty)


@app.post("/api/games/chess/join", response_model=schemas.GameSessionOut)
def join_chess_room(
    data: schemas.ChessRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Join the black seat of a private Chinese-chess room."""
    if _allow_legacy_customer_header() and not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return chess_service.join_room(db, data.room_code, customer_id, data.player_name)


@app.post("/api/games/chess/move", response_model=schemas.GameSessionOut)
def chess_move(
    data: schemas.ChessMoveAction,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Apply a versioned move, resignation or chat and persist its replay."""
    return chess_service.move(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.model_dump(exclude={"room_code", "action", "expected_version"}),
        data.expected_version,
    )


@app.get("/api/games/chess/{room_code}/state", response_model=schemas.GameSessionOut)
def chess_state(
    room_code: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return a member-authorized persisted Chinese-chess board."""
    return chess_service.get_state(db, room_code, customer_id)


@app.get("/api/games/chess/{game_id}/history", response_model=schemas.ChessHistoryOut)
def chess_history(
    game_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return a durable move replay only to an original room member."""
    return chess_service.history(db, game_id, customer_id)


@app.post("/api/games/{game_type}/ai/move", response_model=schemas.GameSessionOut)
def force_game_ai_move(
    game_type: str,
    data: schemas.AIMoveRequest,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Advance an AI only from current server state; arbitrary client boards are rejected."""
    if game_type != "chinese_chess":
        raise HTTPException(status_code=409, detail="该游戏会在正常动作接口中自动执行 AI 回合")
    return chess_service.force_ai_move(db, data.room_code, customer_id, data.expected_version)


@app.get("/api/games/ai/players", response_model=list[schemas.AIPlayerOut])
def game_ai_players(db: Session = Depends(get_db)):
    """List enabled game AI personas and their transparent difficulty metadata."""
    return game_data_service.ensure_ai_catalog(db)


@app.get("/api/games/ranking", response_model=schemas.GameRankingOut)
def game_ranking(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return private personal totals and a shared-room monthly ranking."""
    return game_data_service.ranking(db, customer_id)


@app.get("/api/games/memories/my", response_model=list[schemas.GameMemoryOut])
def my_game_memories(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return only the current device's game highlights."""
    return game_data_service.list_memories(db, customer_id)


@app.get("/api/games/ai/summary", response_model=schemas.DailyAISummaryOut)
def game_ai_summary(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return an explainable rule-based daily companion summary."""
    return game_data_service.daily_summary(db, customer_id)


@app.get("/api/games/{room_code}/state", response_model=schemas.GameSessionOut)
def versioned_game_state(
    room_code: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Read viewer-filtered V2.5 state through one stable endpoint."""
    return animal_service.get_any_state(db, room_code, customer_id)


@app.get("/api/games/achievements", response_model=list[schemas.AchievementOut])
def game_achievements(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return persistent achievement progress for the current device."""
    return achievement_service.achievement_catalog(db, customer_id)


@app.get("/api/games/tasks/my", response_model=list[schemas.LoveTaskOut])
def my_game_love_tasks(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return post-game couple tasks created by completed landlord rounds."""
    from games.core.service import list_love_tasks

    return list_love_tasks(db, customer_id)


@app.post("/api/games/tasks/{task_id}/complete", response_model=schemas.LoveTaskOut)
def complete_game_love_task(
    task_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Mark an owned post-game couple promise as completed."""
    from games.core.service import complete_love_task

    return complete_love_task(db, customer_id, task_id)


@app.post("/api/games/dice/rooms", response_model=schemas.DiceRoomOut)
async def create_dice_room(data: schemas.DiceRoomCreate, db: Session = Depends(get_db)):
    """Compatibility endpoint for already uploaded 1.x clients."""
    if not _allow_legacy_customer_header():
        raise HTTPException(status_code=410, detail="请升级小程序后从统一游戏大厅创建房间")
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


def _persist_completed_game(event: dict):
    with SessionLocal() as db:
        result = dict(event.get("result") or {})
        result["_settlement"] = "pending"
        record = crud.finish_game_room(
            db,
            event["room_code"],
            event.get("winner_id"),
            event.get("duration", 0),
            result,
            event.get("round_number", 1),
        )
        settle_game_rewards(
            db,
            record,
            event.get("players") or [],
            event.get("winner_id"),
        )
        replay_state = result.get("final_state") or result
        game_recovery_service.save_replay(db, record, replay_state)
        for player_id in (
            item for item in (event.get("players") or [])
            if not str(item).startswith("ai_")
        ):
            couple_profile_service.record_memory_once(
                db,
                player_id,
                "GAME",
                "一起完成了一局游戏",
                f"{event.get('game_type', 'game')} · {event.get('duration', 0)} 秒",
                "GAME_RECORD",
                record.id,
                record.created_at.date(),
            )
            notification_service.create_notification(
                db,
                player_id,
                "GAME_FINISHED",
                "对局结果已经保存",
                "战绩、积分和回放都可以在一起玩中查看。",
                record.id,
            )
        record.result = {**(record.result or {}), "_settlement": "complete"}
        db.commit()
        db.refresh(record)
        return record


async def _persist_completed_game_with_retry(event: dict):
    """Persist a completed round off the event loop, retrying one transient failure."""
    last_error = None
    for attempt in range(2):
        try:
            return await asyncio.to_thread(_persist_completed_game, event)
        except Exception as error:  # Database drivers expose different transient errors.
            last_error = error
            if attempt == 0:
                await asyncio.sleep(0.2)
    raise last_error


async def _game_room_socket(
    websocket: WebSocket,
    room_code: str,
    protocol: str,
    forced_game_type: str | None = None,
):
    await websocket.accept()
    player_id = None
    joined_room = False
    normalized_room_code = room_code.strip().upper()
    game_type = forced_game_type or "unknown"
    room_session = None
    try:
        try:
            with SessionLocal() as db:
                room_record = crud.get_game_room(db, normalized_room_code)
                game_type = room_record.game_type
                is_warm_gomoku_room = (
                    game_type == "gomoku"
                    and await game_room_manager.has_room(normalized_room_code)
                )
                if room_record.status == "finished" and not is_warm_gomoku_room:
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
                await game_room_manager.restore_players(
                    normalized_room_code,
                    crud.list_game_players(db, normalized_room_code),
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
        requested_game = str(
            join_message.get("game") or forced_game_type or game_type
        ).lower()
        if str(join_message.get("type") or "").lower() != "join":
            await _send_game_error(websocket, "请先加入房间", game_type, protocol)
            await websocket.close(code=4400)
            return
        if requested_game != game_type:
            await _send_game_error(websocket, "游戏类型与房间不匹配", game_type, protocol)
            await websocket.close(code=4400)
            return
        customer_token = str(join_data.get("customer_token") or "").strip()
        if customer_token:
            try:
                with SessionLocal() as db:
                    player_id = customer_service.authenticate(db, customer_token).id
            except HTTPException:
                await _send_game_error(websocket, "设备登录已失效", game_type, protocol)
                await websocket.close(code=4401)
                return
        elif _allow_legacy_customer_header() and secrets.compare_digest(
            str(join_data.get("invite_code") or ""), get_admin_invite_code()
        ):
            logger.warning("deprecated_websocket_player_id game=%s", game_type)
            player_id = str(join_data.get("player_id") or "").strip()[:100]
        else:
            await _send_game_error(websocket, "请重新验证设备后加入房间", game_type, protocol)
            await websocket.close(code=4401)
            return
        player_name = str(join_data.get("name") or "玩家").strip()[:20] or "玩家"
        if not player_id:
            await _send_game_error(websocket, "玩家标识不能为空", game_type, protocol)
            await websocket.close(code=4400)
            return
        try:
            with SessionLocal() as db:
                stored_player = crud.join_game_room(db, normalized_room_code, player_id)
                if customer_token:
                    room_session = crud.issue_room_session_token(db, stored_player)
                stored_players = crud.list_game_players(db, normalized_room_code)
        except HTTPException as error:
            await _send_game_error(websocket, str(error.detail), game_type, protocol)
            await websocket.close(code=4404)
            return
        await game_room_manager.restore_players(normalized_room_code, stored_players)
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
        joined_room = True
        if room_session:
            await websocket.send_json({
                "type": "session",
                "game": game_type,
                "room_code": normalized_room_code,
                "data": {
                    "room_session_token": room_session[0],
                    "expires_at": room_session[1].isoformat(),
                },
            })
        _sync_game_room_status(
            normalized_room_code,
            await game_room_manager.room_status(normalized_room_code),
        )
        while True:
            action = await websocket.receive_json()
            action_type = str(action.get("type") or "").lower()
            if action_type == "ping":
                pong = {"type": "pong"}
                if protocol != "legacy":
                    pong.update(game=game_type, data={})
                await websocket.send_json(pong)
                continue
            error = await game_room_manager.handle(normalized_room_code, player_id, action)
            if error:
                await _send_game_error(websocket, error, game_type, protocol)
                continue
            # Publish lifecycle status before slower score/replay/notification
            # settlement so HTTP readers never observe a stale playing room.
            _sync_game_room_status(
                normalized_room_code,
                await game_room_manager.room_status(normalized_room_code),
                allow_restart=action_type == "rematch",
            )
            completed_event = await game_room_manager.consume_completed_event(
                normalized_room_code
            )
            if completed_event:
                try:
                    await _persist_completed_game_with_retry(completed_event)
                except Exception:
                    await game_room_manager.restore_completed_event(
                        normalized_room_code,
                        completed_event,
                    )
                    logger.exception(
                        "Failed to persist completed %s round in room %s",
                        game_type,
                        normalized_room_code,
                    )
                    await _send_game_error(
                        websocket,
                        "对局已经结束，但成长记录暂时保存失败",
                        game_type,
                        protocol,
                    )
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if player_id and joined_room:
            await game_room_manager.leave(normalized_room_code, player_id, websocket)
            try:
                with SessionLocal() as db:
                    crud.mark_game_player_disconnected(db, normalized_room_code, player_id)
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
        invalid_image = any(marker in str(error) for marker in ("有效图片", "扩展名", "图片内容"))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if invalid_image else status.HTTP_503_SERVICE_UNAVAILABLE,
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
async def submit_order(
    data: schemas.OrderCreate,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    # Test/dev compatibility is explicitly opt-in. Production never trusts the body id.
    if not customer_id and _allow_legacy_customer_header() and data.customer_id:
        customer_id = data.customer_id.strip()[:100]
        logger.warning("deprecated_order_body_customer_id")
    if not customer_id:
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    order = crud.create_order(db, data.model_copy(update={"customer_id": customer_id}))
    if order.customer_id:
        user_service.ensure_user(db, order.customer_id)
        couple_profile_service.record_first_memory(
            db,
            order.customer_id,
            "FIRST_MEAL",
            "第一次在这里点菜",
            "从这一顿开始，把喜欢慢慢写进共同菜单。",
            "ORDER",
            order.id,
            order.created_at.date(),
        )
    notification_service.create_notification(
        db,
        "admin",
        "ORDER_CREATED",
        f"收到新点菜单 #{order.id}",
        "她已经选好想吃的菜，去小厨房看看吧。",
        order.id,
    )
    await order_event_hub.broadcast("order_created", order.id)
    return order


@app.post("/api/orders/{order_id}/repeat-preview", response_model=schemas.OrderRepeatDraft)
def repeat_order(
    order_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return crud.repeat_order_draft(db, order_id, customer_id)


@app.post("/api/orders/repeat/{order_id}", response_model=schemas.OrderRepeatDraft, deprecated=True)
def repeat_order_legacy(
    order_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    logger.warning("deprecated_endpoint endpoint=/api/orders/repeat/{order_id}")
    return crud.repeat_order_draft(db, order_id, customer_id)


@app.get(
    "/api/orders",
    response_model=list[schemas.OrderOut],
    dependencies=[Depends(verify_admin_token)],
)
def orders(db: Session = Depends(get_db)):
    return crud.list_orders(db)


@app.get("/api/admin/orders", response_model=schemas.AdminOrderPage, dependencies=[Depends(verify_admin_token)])
def admin_orders(
    status: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    from datetime import date

    try:
        parsed_start = date.fromisoformat(start_date) if start_date else None
        parsed_end = date.fromisoformat(end_date) if end_date else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail="日期必须使用 YYYY-MM-DD") from error
    return crud.list_admin_orders(db, status, cursor, limit, keyword, parsed_start, parsed_end)


@app.get("/api/orders/me", response_model=list[schemas.OrderOut])
def my_orders(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return crud.list_customer_orders(db, customer_id)


@app.get("/api/orders/my/{legacy_customer_id}", response_model=list[schemas.OrderOut], deprecated=True)
def legacy_my_orders(
    legacy_customer_id: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    logger.warning("deprecated_endpoint endpoint=/api/orders/my/{customer_id}")
    if legacy_customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return crud.list_customer_orders(db, customer_id)


@app.get("/api/orders/{order_id}", response_model=schemas.OrderOut)
def order_detail(
    order_id: int,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    order = crud.get_order(db, order_id)
    if not customer_id and _allow_legacy_customer_header():
        return order
    if not customer_id or order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


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
    previous_status = crud.get_order(db, order_id).status
    order = crud.update_order_status(db, order_id, data.status)
    if order.customer_id and previous_status != order.status:
        notification_service.create_notification(
            db,
            order.customer_id,
            "ORDER_STATUS",
            f"订单 #{order.id}：{order.status}",
            "小厨房有新的进度，点开就能看到。",
            order.id,
        )
        if order.status == "已完成":
            couple_profile_service.record_first_memory(
                db,
                order.customer_id,
                "FIRST_COOK",
                "第一次完成专属晚餐",
                "认真准备的一顿饭，成为了我们的共同记录。",
                "ORDER_COMPLETE",
                order.id,
                order.created_at.date(),
            )
    await order_event_hub.broadcast("order_status_changed", order.id)
    return order


@app.post(
    "/api/admin/orders/{order_id}/rollback",
    response_model=schemas.OrderOut,
    dependencies=[Depends(verify_admin_token)],
)
async def rollback_order_status(order_id: int, db: Session = Depends(get_db)):
    order = crud.rollback_order_status(db, order_id)
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
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    order = crud.get_order(db, order_id)
    if not customer_id and not _allow_legacy_customer_header():
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    if customer_id and order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    review = crud.create_review(db, order_id, data)
    notification_service.create_notification(
        db,
        "admin",
        "ORDER_REVIEW",
        f"订单 #{order_id} 收到 {review.rating} 心评价",
        review.comment or "这顿饭已经留下新的口味反馈。",
        order_id,
    )
    await order_event_hub.broadcast("order_reviewed", order_id)
    return review


@app.get("/api/orders/{order_id}/review", response_model=schemas.ReviewOut)
def order_review(
    order_id: int,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    order = crud.get_order(db, order_id)
    if not customer_id and not _allow_legacy_customer_header():
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    if customer_id and order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
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


@app.get("/api/couple/tasks/today", response_model=schemas.DailyTaskSummary)
def couple_tasks_today(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return task_service.today_summary(db, customer_id)


@app.post("/api/couple/tasks/{task_id}/complete", response_model=schemas.DailyTaskOut)
def complete_couple_task(
    task_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    return task_service.complete_manual_task(db, customer_id, task_id)


@app.post(
    "/api/couple/score/add",
    response_model=schemas.LoveScoreOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_token)],
)
def add_couple_score(
    data: schemas.LoveScoreCreate,
    x_customer_id: str | None = Header(default=None, alias="X-Customer-Id"),
    db: Session = Depends(get_db),
):
    customer_id = (x_customer_id or "").strip()[:100]
    if not customer_id:
        raise HTTPException(status_code=422, detail="请选择积分所属用户")
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
