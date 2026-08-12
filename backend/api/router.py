"""Top-level API router registry.

Route groups are included here as they are migrated out of ``main.py``. Keeping
one registry makes application assembly explicit without changing URL prefixes.
"""

from fastapi import APIRouter

from api.routes import (
    admin,
    auth,
    couple,
    dishes,
    games,
    notifications,
    orders,
    system,
    uploads,
    users,
    websocket,
)


router = APIRouter()
router.include_router(system.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(dishes.router)
router.include_router(notifications.router)
router.include_router(couple.router)
router.include_router(orders.router)
router.include_router(admin.router)
router.include_router(uploads.router)
router.include_router(games.router)
router.include_router(websocket.router)
