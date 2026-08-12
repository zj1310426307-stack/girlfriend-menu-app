"""Authenticated user profile and presence routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import schemas
import user_service
from api.dependencies import get_customer_id
from core.cache import state_cache
from database import get_db


router = APIRouter()


@router.get("/api/users/me", response_model=schemas.UserOut)
def current_user(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the unified profile behind the legacy-compatible customer ID."""
    return user_service.ensure_user(db, customer_id)


@router.put("/api/users/me", response_model=schemas.UserOut)
def update_current_user(
    data: schemas.UserUpdate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Update the authenticated customer's display profile."""
    user = user_service.ensure_user(db, customer_id)
    user.nickname = data.nickname
    user.avatar = data.avatar
    db.commit()
    db.refresh(user)
    return user


@router.post("/api/users/presence")
def heartbeat(customer_id: str = Depends(get_customer_id)):
    """Refresh the optional Redis online marker used by private rooms."""
    state_cache.touch_presence(customer_id)
    return {"online": True, "ttl_seconds": 90}
