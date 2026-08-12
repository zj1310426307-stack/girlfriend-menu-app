"""Order business rules and post-transaction product orchestration."""

from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from love_score import record_score
from repositories import orders as orders_repository
from task_service import complete_task_type


ORDER_STATUS_TRANSITIONS = {
    "待接单": {"已接单", "暂时做不了"},
    "已接单": {"制作中", "暂时做不了"},
    "制作中": {"已完成", "暂时做不了"},
    "已完成": set(),
    "暂时做不了": set(),
}


def get_order(db: Session, order_id: int) -> models.Order:
    """Return one order or preserve the public 404 detail."""
    order = orders_repository.find(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


def create_order(db: Session, data: schemas.OrderCreate) -> models.Order:
    """Validate, snapshot and commit one order before optional repeat rewards."""
    if data.idempotency_key:
        existing = orders_repository.find_by_idempotency_key(
            db,
            data.idempotency_key,
        )
        if existing:
            if existing.customer_id != data.customer_id:
                raise HTTPException(status_code=409, detail="提交标识已经被使用")
            return existing

    dish_ids = {item.dish_id for item in data.items}
    dishes = orders_repository.list_active_dishes(db, dish_ids)
    dish_map = {dish.id: dish for dish in dishes}
    missing = dish_ids - dish_map.keys()
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"菜品不存在或已经下架：{sorted(missing)}",
        )

    if data.source_order_id:
        source_order = get_order(db, data.source_order_id)
        if not data.customer_id or source_order.customer_id != data.customer_id:
            # Ownership mismatch deliberately looks identical to a missing order.
            raise HTTPException(status_code=404, detail="订单不存在")

    order = models.Order(
        note=data.note,
        desired_time=data.desired_time,
        desired_at=(
            data.desired_at.replace(tzinfo=timezone.utc)
            if data.desired_at and data.desired_at.tzinfo is None
            else data.desired_at.astimezone(timezone.utc) if data.desired_at else None
        ),
        customer_id=data.customer_id,
        source_order_id=data.source_order_id,
        idempotency_key=data.idempotency_key,
        status_updated_at=datetime.now(timezone.utc),
    )
    order = orders_repository.create(db, order, data.items, dish_map)
    if order.source_order_id and order.customer_id:
        record_score(
            db,
            order.customer_id,
            "SPECIAL_EVENT",
            2,
            "再次点了喜欢的菜单",
            order.id,
        )
    return order


def repeat_order_draft(
    db: Session,
    order_id: int,
    customer_id: str,
) -> dict:
    """Build an editable repeat draft without writing or mutating an order."""
    order = get_order(db, order_id)
    if not order.customer_id or order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")

    dish_ids = {item.dish_id for item in order.items}
    current_dishes = orders_repository.list_dishes(db, dish_ids)
    dish_map = {dish.id: dish for dish in current_dishes}
    items = []
    unavailable_names = []
    for item in order.items:
        dish = dish_map.get(item.dish_id)
        available = bool(dish and dish.is_active)
        if not available:
            unavailable_names.append(item.dish_name)
        items.append(
            {
                "dish_id": item.dish_id,
                "name": dish.name if dish else item.dish_name,
                "description": dish.description if dish else "",
                "category": dish.category if dish else "",
                "price": dish.price if dish else item.price,
                "image_url": dish.image_url if dish else "",
                "quantity": item.quantity,
                "available": available,
            }
        )
    return {
        "source_order_id": order.id,
        "note": order.note,
        "items": items,
        "unavailable_names": unavailable_names,
    }


def list_orders(db: Session) -> list[models.Order]:
    """List all submitted orders for administrator callers."""
    return orders_repository.list_all(db)


def list_admin_orders(
    db: Session,
    status: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Return the deployed filtered administrator cursor page unchanged."""
    return orders_repository.list_admin_page(
        db,
        status,
        cursor,
        limit,
        keyword,
        start_date,
        end_date,
    )


def list_customer_orders(db: Session, customer_id: str) -> list[models.Order]:
    """List only orders associated with one authenticated customer."""
    return orders_repository.list_customer(db, customer_id)


def update_order_status(
    db: Session,
    order_id: int,
    status: str,
    actor_id: str = "admin",
) -> models.Order:
    """Apply one legal forward transition, then settle completion rewards."""
    order = get_order(db, order_id)
    if status == order.status:
        return order
    if status not in ORDER_STATUS_TRANSITIONS.get(order.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"订单不能从“{order.status}”直接变为“{status}”",
        )
    previous = order.status
    order.status = status
    order.status_updated_at = datetime.now(timezone.utc)
    order = orders_repository.commit_status_event(
        db,
        order,
        previous,
        "ADMIN",
        actor_id,
    )
    if status == "已完成" and order.customer_id:
        record_score(
            db,
            order.customer_id,
            "ORDER_COMPLETE",
            10,
            "完成一次晚餐制作",
            order.id,
        )
        complete_task_type(db, order.customer_id, "MEAL")
    return order


def rollback_order_status(
    db: Session,
    order_id: int,
    actor_id: str = "admin",
) -> models.Order:
    """Restore the latest prior status while preserving append-only audit history."""
    order = get_order(db, order_id)
    if order.status == "已完成":
        raise HTTPException(status_code=409, detail="已完成订单禁止回退，原评价会被完整保留")
    event = orders_repository.find_latest_status_event(db, order.id)
    if not event or not event.from_status:
        raise HTTPException(status_code=409, detail="没有可以撤回的上一步")
    previous = order.status
    order.status = event.from_status
    order.status_updated_at = datetime.now(timezone.utc)
    return orders_repository.commit_status_event(
        db,
        order,
        previous,
        "ADMIN_ROLLBACK",
        actor_id,
    )
