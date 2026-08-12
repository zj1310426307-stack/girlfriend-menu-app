"""Order persistence, query composition and audit-event storage."""

from datetime import date, datetime, time as datetime_time, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

import models
import schemas


def find(db: Session, order_id: int) -> models.Order | None:
    """Find an order by primary key without applying public error semantics."""
    return db.get(models.Order, order_id)


def find_by_idempotency_key(
    db: Session,
    idempotency_key: str,
) -> models.Order | None:
    """Find an earlier submission for request replay protection."""
    return (
        db.query(models.Order)
        .filter(models.Order.idempotency_key == idempotency_key)
        .first()
    )


def list_active_dishes(
    db: Session,
    dish_ids: set[int],
) -> list[models.Dish]:
    """Load only active dishes accepted by new-order validation."""
    return (
        db.query(models.Dish)
        .filter(models.Dish.id.in_(dish_ids), models.Dish.is_active.is_(True))
        .all()
    )


def list_dishes(db: Session, dish_ids: set[int]) -> list[models.Dish]:
    """Load current catalogue rows, including inactive repeat-order items."""
    return db.query(models.Dish).filter(models.Dish.id.in_(dish_ids)).all()


def create(
    db: Session,
    order: models.Order,
    items: list[schemas.OrderItemCreate],
    dish_map: dict[int, models.Dish],
) -> models.Order:
    """Persist an order and immutable item snapshots in the deployed sequence."""
    db.add(order)
    db.flush()
    for item in items:
        dish = dish_map[item.dish_id]
        order.items.append(
            models.OrderItem(
                dish_id=dish.id,
                dish_name=dish.name,
                price=dish.price,
                quantity=item.quantity,
            )
        )
    db.commit()
    db.refresh(order)
    return order


def list_all(db: Session) -> list[models.Order]:
    """Return all orders in the established newest-first order."""
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()


def list_customer(db: Session, customer_id: str) -> list[models.Order]:
    """Return only orders owned by one authenticated customer."""
    return (
        db.query(models.Order)
        .filter(models.Order.customer_id == customer_id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


def list_admin_page(
    db: Session,
    status: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Apply the existing admin filters and cursor-page calculation exactly."""
    safe_limit = max(1, min(int(limit), 50))
    query = db.query(models.Order)
    count_query = db.query(func.count(models.Order.id))
    filters = []
    if status:
        filters.append(models.Order.status == status)
    if cursor:
        filters.append(models.Order.id < cursor)
    if start_date:
        filters.append(
            models.Order.created_at
            >= datetime.combine(start_date, datetime_time.min)
        )
    if end_date:
        filters.append(
            models.Order.created_at
            < datetime.combine(end_date + timedelta(days=1), datetime_time.min)
        )
    if keyword and keyword.strip():
        value = keyword.strip()
        keyword_filter = models.Order.items.any(
            models.OrderItem.dish_name.ilike(f"%{value}%")
        )
        if value.isdigit():
            keyword_filter = or_(models.Order.id == int(value), keyword_filter)
        filters.append(keyword_filter)
    if filters:
        query = query.filter(*filters)
        count_query = count_query.filter(*filters)
    items = query.order_by(models.Order.id.desc()).limit(safe_limit + 1).all()
    has_more = len(items) > safe_limit
    visible = items[:safe_limit]
    return {
        "items": visible,
        "next_cursor": visible[-1].id if has_more and visible else None,
        "total_estimate": count_query.scalar() or 0,
    }


def commit_status_event(
    db: Session,
    order: models.Order,
    previous_status: str,
    actor_type: str,
    actor_id: str,
) -> models.Order:
    """Commit an already-applied status change with one append-only audit row."""
    db.add(
        models.OrderStatusEvent(
            order_id=order.id,
            from_status=previous_status,
            to_status=order.status,
            actor_type=actor_type,
            actor_id=actor_id,
        )
    )
    db.commit()
    db.refresh(order)
    return order


def find_latest_status_event(
    db: Session,
    order_id: int,
) -> models.OrderStatusEvent | None:
    """Return the latest status audit event used by administrator rollback."""
    return (
        db.query(models.OrderStatusEvent)
        .filter(models.OrderStatusEvent.order_id == order_id)
        .order_by(models.OrderStatusEvent.id.desc())
        .first()
    )
