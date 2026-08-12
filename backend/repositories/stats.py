"""Read-only persistence queries for non-game order statistics."""

from sqlalchemy import func
from sqlalchemy.orm import Session

import models


def summary(db: Session) -> dict:
    """Aggregate total, completed and most-recent submitted order facts."""
    total_orders = db.query(func.count(models.Order.id)).scalar() or 0
    completed_orders = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.status == "已完成")
        .scalar()
        or 0
    )
    last_order_at = db.query(func.max(models.Order.created_at)).scalar()
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "last_order_at": last_order_at,
    }


def dishes(db: Session) -> list[dict]:
    """Aggregate ordered quantities and latest order time per dish snapshot."""
    rows = (
        db.query(
            models.OrderItem.dish_id,
            models.OrderItem.dish_name,
            func.sum(models.OrderItem.quantity).label("total_quantity"),
            func.max(models.Order.created_at).label("last_ordered_at"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .group_by(models.OrderItem.dish_id, models.OrderItem.dish_name)
        .order_by(
            func.sum(models.OrderItem.quantity).desc(),
            func.max(models.Order.created_at).desc(),
        )
        .all()
    )
    return [
        {
            "dish_id": row.dish_id,
            "dish_name": row.dish_name,
            "total_quantity": row.total_quantity,
            "last_ordered_at": row.last_ordered_at,
        }
        for row in rows
    ]


def recent_orders(db: Session) -> list[models.Order]:
    """Return the ten most recently submitted orders."""
    return (
        db.query(models.Order)
        .order_by(models.Order.created_at.desc())
        .limit(10)
        .all()
    )
