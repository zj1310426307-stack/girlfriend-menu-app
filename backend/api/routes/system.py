"""Root, liveness and readiness endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.cache import state_cache
from database import engine, get_db
from storage import storage_readiness


router = APIRouter()


@router.get("/")
def root():
    """Return the original API welcome payload."""
    return {"message": "女朋友专属点菜小程序 API 正常运行"}


@router.get("/api/health", include_in_schema=False)
def health_check():
    """Provide a lightweight liveness endpoint for Render monitoring."""
    return {"status": "ok", "service": "girlfriend-menu-api"}


@router.get("/api/ready", include_in_schema=False)
def readiness_check(db: Session = Depends(get_db)):
    """Verify database reachability and expose the existing release blockers."""
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
