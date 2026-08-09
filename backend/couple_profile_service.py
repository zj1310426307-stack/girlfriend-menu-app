"""Couple memories, anniversaries, timeline and long-term aggregate profile."""
from __future__ import annotations

from datetime import date, datetime, time

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from user_service import ensure_user


MEMORY_TYPES = {"FIRST_MEAL", "FIRST_COOK", "TRAVEL", "GAME", "ANNIVERSARY", "OTHER"}


def add_memory(db: Session, user_code: str, data) -> models.CoupleMemory:
    """Create an editable private timeline entry."""
    user = ensure_user(db, user_code)
    item = models.CoupleMemory(user_id=user.id, **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


def record_memory_once(db: Session, user_code: str, memory_type: str, title: str, content: str, source_type: str, source_id: int, event_date: date | None = None) -> None:
    """Create one automatic business memory exactly once per source."""
    user = ensure_user(db, user_code)
    exists = db.query(models.CoupleMemory.id).filter(models.CoupleMemory.user_id == user.id, models.CoupleMemory.source_type == source_type, models.CoupleMemory.source_id == source_id).first()
    if exists:
        return
    db.add(models.CoupleMemory(user_id=user.id, type=memory_type, title=title, content=content, event_date=event_date or date.today(), source_type=source_type, source_id=source_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def record_first_memory(db: Session, user_code: str, memory_type: str, title: str, content: str, source_type: str, source_id: int, event_date: date | None = None) -> None:
    """Record only the first occurrence of a milestone type for one user."""
    user = ensure_user(db, user_code)
    if db.query(models.CoupleMemory.id).filter(models.CoupleMemory.user_id == user.id, models.CoupleMemory.type == memory_type).first():
        return
    record_memory_once(db, user_code, memory_type, title, content, source_type, source_id, event_date)


def list_memories(db: Session, user_code: str, limit: int = 100) -> list[models.CoupleMemory]:
    """Return the current user's editable timeline in reverse chronology."""
    user = ensure_user(db, user_code)
    return db.query(models.CoupleMemory).filter(models.CoupleMemory.user_id == user.id).order_by(models.CoupleMemory.event_date.desc(), models.CoupleMemory.id.desc()).limit(max(1, min(limit, 200))).all()


def delete_memory(db: Session, user_code: str, memory_id: int) -> None:
    """Delete only a memory owned by the current user."""
    user = ensure_user(db, user_code)
    item = db.query(models.CoupleMemory).filter(models.CoupleMemory.id == memory_id, models.CoupleMemory.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="共同记忆不存在")
    db.delete(item); db.commit()


def add_date(db: Session, user_code: str, data) -> models.CoupleDate:
    """Create one anniversary with bounded advance reminder days."""
    user = ensure_user(db, user_code)
    item = models.CoupleDate(user_id=user.id, **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


def list_dates(db: Session, user_code: str) -> list[models.CoupleDate]:
    """Return all anniversaries owned by the current user."""
    user = ensure_user(db, user_code)
    return db.query(models.CoupleDate).filter(models.CoupleDate.user_id == user.id).order_by(models.CoupleDate.date).all()


def delete_date(db: Session, user_code: str, date_id: int) -> None:
    """Delete one owned anniversary."""
    user = ensure_user(db, user_code)
    item = db.query(models.CoupleDate).filter(models.CoupleDate.id == date_id, models.CoupleDate.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="纪念日不存在")
    db.delete(item); db.commit()


def _next_date(items: list[models.CoupleDate]) -> tuple[models.CoupleDate | None, int | None]:
    """Calculate the nearest upcoming one-off or yearly anniversary."""
    today = date.today(); candidates = []
    for item in items:
        target = item.date
        if item.repeat_type == "YEARLY":
            try: target = target.replace(year=today.year)
            except ValueError: target = date(today.year, 2, 28)
            if target < today:
                try: target = target.replace(year=today.year + 1)
                except ValueError: target = date(today.year + 1, 2, 28)
        if target >= today: candidates.append(((target - today).days, item))
    if not candidates: return None, None
    days, item = min(candidates, key=lambda entry: entry[0])
    return item, days


def profile_summary(db: Session, user_code: str) -> dict:
    """Aggregate relationship age, records, meals, games and next anniversary."""
    user = ensure_user(db, user_code)
    dates = list_dates(db, user_code)
    relationship = next(
        (
            item
            for item in dates
            if item.repeat_type == "YEARLY"
            and any(keyword in item.title for keyword in ("恋爱", "在一起", "相识"))
        ),
        None,
    )
    start = relationship.date if relationship else user.created_at.date()
    month_start = datetime.combine(date.today().replace(day=1), time.min)
    meals = db.query(func.count(models.Order.id)).filter(models.Order.customer_id == user_code, models.Order.created_at >= month_start).scalar() or 0
    games = db.query(func.count(models.GameRecord.id)).join(models.GamePlayer, models.GamePlayer.room_id == models.GameRecord.room_id).filter(models.GamePlayer.player_id == user_code, models.GameRecord.created_at >= month_start).scalar() or 0
    record_count = db.query(func.count(models.CoupleMemory.id)).filter(models.CoupleMemory.user_id == user.id).scalar() or 0
    next_item, days = _next_date(dates)
    return {"days_together": max(1, (date.today() - start).days + 1), "record_count": int(record_count), "month_meals": int(meals), "month_games": int(games), "next_date_title": next_item.title if next_item else None, "next_date_days": days}


def statistics(db: Session, user_code: str) -> dict:
    """Return one durable cross-domain couple analytics payload."""
    meals = db.query(func.count(models.Order.id)).filter(models.Order.customer_id == user_code).scalar() or 0
    games = db.query(func.count(models.GameRecord.id)).join(models.GamePlayer, models.GamePlayer.room_id == models.GameRecord.room_id).filter(models.GamePlayer.player_id == user_code).scalar() or 0
    interactions = db.query(func.count(models.LoveScore.id)).filter(models.LoveScore.customer_id == user_code).scalar() or 0
    score = db.query(func.coalesce(func.sum(models.LoveScore.score), 0)).filter(models.LoveScore.customer_id == user_code).scalar() or 0
    favorite = db.query(models.OrderItem.dish_name, func.sum(models.OrderItem.quantity)).join(models.Order, models.Order.id == models.OrderItem.order_id).filter(models.Order.customer_id == user_code).group_by(models.OrderItem.dish_name).order_by(func.sum(models.OrderItem.quantity).desc()).first()
    popular = db.query(models.GameRecord.game_type, func.count(models.GameRecord.id)).join(models.GamePlayer, models.GamePlayer.room_id == models.GameRecord.room_id).filter(models.GamePlayer.player_id == user_code).group_by(models.GameRecord.game_type).order_by(func.count(models.GameRecord.id).desc()).first()
    return {"meals": int(meals), "games": int(games), "interactions": int(interactions), "love_score": int(score), "favorite_dish": favorite[0] if favorite else None, "favorite_game": popular[0] if popular else None}
