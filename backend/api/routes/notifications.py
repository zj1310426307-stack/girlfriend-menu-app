"""Authenticated notification routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import notification_service
import schemas
from api.dependencies import get_customer_id
from database import get_db


router = APIRouter()


@router.get("/api/notifications", response_model=list[schemas.NotificationOut])
def notifications(
    unread_only: bool = False,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """List notifications after materializing any due anniversary reminders."""
    notification_service.generate_anniversary_reminders(db, customer_id)
    return notification_service.list_notifications(db, customer_id, unread_only)


@router.get("/api/notifications/unread-count")
def notification_unread_count(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the unread counter for the authenticated customer."""
    notification_service.generate_anniversary_reminders(db, customer_id)
    return {"count": notification_service.unread_count(db, customer_id)}


@router.patch(
    "/api/notifications/{notification_id}/read",
    response_model=schemas.NotificationOut,
)
def read_notification(
    notification_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Mark one owned notification as read."""
    return notification_service.mark_read(db, customer_id, notification_id)
