"""FastAPI application assembly.

Business endpoints live under ``api.routes``. This module owns only process
lifecycle, middleware, static mounting and top-level router registration.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import crud
import game_data_service
import game_maintenance
import models
import notification_service
import user_service
from api.router import router as api_router
from core.game_room_lease import INSTANCE_ID, renew_room_leases
from core.rate_limit import RateLimitExceeded, rate_limiter
from database import Base, SessionLocal, engine, ensure_compatible_schema
from game_runtime import game_room_manager
from seed import seed_achievements, seed_dishes, seed_game_events, seed_games
from storage import UPLOAD_DIR, ensure_upload_directory


logger = logging.getLogger(__name__)
ensure_upload_directory()


async def _maintenance_loop():
    """Generate durable anniversary reminders on the existing six-hour cadence."""
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
    """Repair settlements, resolve clocks and archive inactive rooms every minute."""
    while True:
        await asyncio.sleep(60)
        try:
            with SessionLocal() as db:
                timeout_result = game_maintenance.resolve_turn_timeouts(db)
                settlement_result = game_maintenance.reconcile_game_settlements(db)
                expired_codes = crud.expire_stale_game_rooms(db)
            removed = await game_room_manager.cleanup_expired(expired_codes)
            if removed:
                logger.info("expired_game_rooms count=%s", len(removed))
            if timeout_result["finished"] or settlement_result["repaired"]:
                logger.info(
                    "game_maintenance timeouts=%s settlements=%s",
                    timeout_result,
                    settlement_result,
                )
        except Exception:
            logger.exception("game room cleanup failed")


async def _game_lease_heartbeat_loop():
    """Keep ownership only for rooms that still have local live sockets."""
    while True:
        await asyncio.sleep(10)
        try:
            room_codes = await game_room_manager.active_room_codes()
            with SessionLocal() as db:
                renew_room_leases(db, room_codes)
        except Exception:
            logger.exception(
                "game room lease heartbeat failed instance=%s",
                INSTANCE_ID,
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local compatibility schema, seed catalogues and own background tasks."""
    ensure_upload_directory()
    # Production startup runs ``alembic upgrade head`` before Uvicorn. The
    # compatibility path remains restricted to local development and tests.
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
        asyncio.create_task(_game_lease_heartbeat_loop()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


def get_frontend_origins() -> list[str]:
    """Parse the optional allow-list for diagnostics or a future browser client."""
    raw_urls = os.getenv("FRONTEND_URL", "")
    return [url.strip().rstrip("/") for url in raw_urls.split(",") if url.strip()]


app = FastAPI(title="情侣智能厨房管家 API", version="2.11.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.include_router(api_router)


@app.middleware("http")
async def request_log(request: Request, call_next):
    """Emit one privacy-safe structured line and enforce shared request limits."""
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
            rate_limiter.check(
                f"{protected_scope[0]}:{client}",
                protected_scope[1],
                protected_scope[2],
            )
        except RateLimitExceeded:
            return Response(status_code=429, content="Too many requests")
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise
    duration = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "request id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response
