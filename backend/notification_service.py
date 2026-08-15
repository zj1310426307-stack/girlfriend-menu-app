"""Durable in-app notifications shared by food, games and anniversaries."""
from contextlib import nullcontext
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from core.telemetry import trace_span
from user_service import ensure_user


def create_notification(
    db: Session,
    user_code: str,
    kind: str,
    title: str,
    content: str,
    related_id: int | None = None,
    *,
    trace_persist: bool = False,
) -> models.Notification:
    """Create one durable notification for a unified identity."""
    scope = (
        trace_span("notification.persist", {"result": "created"})
        if trace_persist
        else nullcontext()
    )
    with scope:
        user = ensure_user(db, user_code)
        item = models.Notification(
            user_id=user.id,
            type=kind,
            title=title[:100],
            content=content,
            related_id=related_id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item


def create_notification_once(
    db: Session,
    user_code: str,
    kind: str,
    title: str,
    content: str,
    related_id: int,
    *,
    trace_persist: bool = False,
) -> models.Notification:
    """Create one notification per user/type/source during retryable workflows."""
    user = ensure_user(db, user_code)
    existing = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user.id,
            models.Notification.type == kind,
            models.Notification.related_id == related_id,
        )
        .first()
    )
    if existing:
        return existing
    return create_notification(
        db,
        user_code,
        kind,
        title,
        content,
        related_id,
        trace_persist=trace_persist,
    )


def list_notifications(db: Session, user_code: str, unread_only: bool = False, limit: int = 50) -> list[models.Notification]:
    """Return newest notifications owned by the current device."""
    user = ensure_user(db, user_code)
    query = db.query(models.Notification).filter(models.Notification.user_id == user.id)
    if unread_only:
        query = query.filter(models.Notification.is_read.is_(False))
    return query.order_by(models.Notification.created_at.desc()).limit(max(1, min(limit, 100))).all()


def mark_read(db: Session, user_code: str, notification_id: int) -> models.Notification:
    """Mark one owned notification read, rejecting cross-user access."""
    user = ensure_user(db, user_code)
    item = db.query(models.Notification).filter(models.Notification.id == notification_id, models.Notification.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="通知不存在")
    item.is_read = True
    db.commit(); db.refresh(item)
    return item


def unread_count(db: Session, user_code: str) -> int:
    """Return the current user's unread badge count."""
    user = ensure_user(db, user_code)
    return db.query(models.Notification).filter(models.Notification.user_id == user.id, models.Notification.is_read.is_(False)).count()


def generate_anniversary_reminders(db: Session, user_code: str) -> None:
    """Create idempotent near-term anniversary reminders for the current year."""
    user = ensure_user(db, user_code)
    today = date.today()
    for item in db.query(models.CoupleDate).filter(models.CoupleDate.user_id == user.id).all():
        target = item.date
        if item.repeat_type == "YEARLY":
            try:
                target = target.replace(year=today.year)
            except ValueError:
                target = date(today.year, 2, 28)
            if target < today:
                target = target.replace(year=today.year + 1)
        days = (target - today).days
        if 0 <= days <= item.reminder_days:
            exists = db.query(models.Notification.id).filter(models.Notification.user_id == user.id, models.Notification.type == "ANNIVERSARY", models.Notification.related_id == item.id, models.Notification.created_at >= datetime.combine(today, datetime.min.time())).first()
            if not exists:
                create_notification(
                    db,
                    user_code,
                    "ANNIVERSARY",
                    f"距离{item.title}还有 {days} 天",
                    "准备一个只属于你们的小纪念吧。",
                    item.id,
                    trace_persist=True,
                )
