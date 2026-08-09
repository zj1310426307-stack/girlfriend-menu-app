"""Compact operational dashboard assembled from durable business tables."""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from core.cache import state_cache


def admin_dashboard(db: Session) -> dict:
    """Return today's cross-domain indicators without mutating source data."""
    start = datetime.combine(date.today(), time.min)
    orders = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.created_at >= start)
        .scalar()
        or 0
    )
    games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.created_at >= start)
        .scalar()
        or 0
    )
    score = (
        db.query(func.coalesce(func.sum(models.LoveScore.score), 0))
        .filter(models.LoveScore.created_at >= start)
        .scalar()
        or 0
    )
    dish = (
        db.query(models.OrderItem.dish_name, func.sum(models.OrderItem.quantity))
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .group_by(models.OrderItem.dish_name)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .first()
    )
    game = (
        db.query(models.GameRecord.game_type, func.count(models.GameRecord.id))
        .group_by(models.GameRecord.game_type)
        .order_by(func.count(models.GameRecord.id).desc())
        .first()
    )
    return {
        "today_orders": int(orders),
        "today_games": int(games),
        "today_score": int(score),
        "popular_dish": dish[0] if dish else None,
        "popular_game": game[0] if game else None,
        "redis": "ready" if state_cache.enabled else "optional-disabled",
    }
