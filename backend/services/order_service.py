"""Order business rules and post-transaction product orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import couple_profile_service
import models
import notification_service
import schemas
from love_score import record_score
from realtime_events import order_event_hub
from repositories import orders as orders_repository
from task_service import complete_task_type


logger = logging.getLogger(__name__)


ORDER_STATUS_TRANSITIONS = {
    "待接单": {"已接单", "暂时做不了"},
    "已接单": {"制作中", "暂时做不了"},
    "制作中": {"已完成", "暂时做不了"},
    "已完成": set(),
    "暂时做不了": set(),
}


@dataclass(frozen=True)
class OrderCreationResult:
    """Expose whether persistence created a new order or replayed an earlier one."""

    order: models.Order
    created: bool


@dataclass(frozen=True)
class OrderStatusMutationResult:
    """Describe a committed status result and whether this call changed it."""

    order: models.Order
    changed: bool
    previous_status: str


def get_order(db: Session, order_id: int) -> models.Order:
    """Return one order or preserve the public 404 detail."""
    order = orders_repository.find(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


def _idempotent_replay(
    db: Session,
    data: schemas.OrderCreate,
) -> models.Order | None:
    """Return an owned replay while preserving the public key-conflict response."""
    if not data.idempotency_key:
        return None
    existing = orders_repository.find_by_idempotency_key(db, data.idempotency_key)
    if existing and existing.customer_id != data.customer_id:
        raise HTTPException(status_code=409, detail="提交标识已经被使用")
    return existing


def create_order_result(db: Session, data: schemas.OrderCreate) -> OrderCreationResult:
    """Validate and commit one order while distinguishing idempotent replays."""
    existing = _idempotent_replay(db, data)
    if existing:
        return OrderCreationResult(order=existing, created=False)

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
    try:
        order = orders_repository.create(db, order, data.items, dish_map)
    except IntegrityError:
        # A concurrent request may win the unique idempotency-key insert after
        # our initial lookup. Recover that committed order instead of leaking 500.
        db.rollback()
        existing = _idempotent_replay(db, data)
        if existing:
            return OrderCreationResult(order=existing, created=False)
        raise
    return OrderCreationResult(order=order, created=True)


def _run_post_commit_effect(
    db: Session,
    result: OrderCreationResult,
    effect_name: str,
    effect: Callable[[], object],
    *,
    compensable: bool,
) -> bool:
    """Run one optional effect without changing an already-committed order result."""
    order_id = result.order.id
    try:
        effect()
        return True
    except Exception:
        logger.exception(
            "order_post_commit_effect_failed effect=%s order_id=%s "
            "created=%s compensable=%s",
            effect_name,
            order_id,
            str(result.created).lower(),
            str(compensable).lower(),
        )
        try:
            db.rollback()
        except Exception:
            logger.exception(
                "order_post_commit_rollback_failed effect=%s order_id=%s",
                effect_name,
                order_id,
            )
        return False


def _run_committed_order_effect(
    db: Session,
    operation: str,
    order_id: int,
    effect_name: str,
    effect: Callable[[], object],
    *,
    compensable: bool,
) -> bool:
    """Isolate one optional effect from an already-committed order mutation."""
    try:
        effect()
        return True
    except Exception:
        logger.exception(
            "order_committed_effect_failed operation=%s effect=%s "
            "order_id=%s compensable=%s",
            operation,
            effect_name,
            order_id,
            str(compensable).lower(),
        )
        try:
            db.rollback()
        except Exception:
            logger.exception(
                "order_committed_effect_rollback_failed operation=%s "
                "effect=%s order_id=%s",
                operation,
                effect_name,
                order_id,
            )
        return False


def _ensure_repeat_reward(
    db: Session,
    order_id: int,
    customer_id: str | None,
    source_order_id: int | None,
) -> None:
    """Ensure a repeat-order reward; the score source constraint makes retries safe."""
    if source_order_id and customer_id:
        record_score(
            db,
            customer_id,
            "SPECIAL_EVENT",
            2,
            "再次点了喜欢的菜单",
            order_id,
        )


def _ensure_first_meal_memory(
    db: Session,
    order_id: int,
    customer_id: str,
    created_at: datetime,
) -> None:
    """Ensure the customer's first-meal memory using its existing source identity."""
    couple_profile_service.record_first_memory(
        db,
        customer_id,
        "FIRST_MEAL",
        "第一次在这里点菜",
        "从这一顿开始，把喜欢慢慢写进共同菜单。",
        "ORDER",
        order_id,
        created_at.date(),
    )


def _ensure_order_created_notification(db: Session, order_id: int) -> None:
    """Ensure sequential idempotent replays create one administrator notification."""
    notification_service.create_notification_once(
        db,
        "admin",
        "ORDER_CREATED",
        f"收到新点菜单 #{order_id}",
        "她已经选好想吃的菜，去小厨房看看吧。",
        order_id,
    )


def create_order(db: Session, data: schemas.OrderCreate) -> models.Order:
    """Preserve the internal creation API while safely settling repeat rewards."""
    result = create_order_result(db, data)
    order_id = result.order.id
    customer_id = result.order.customer_id
    source_order_id = result.order.source_order_id
    _run_post_commit_effect(
        db,
        result,
        "repeat_reward",
        lambda: _ensure_repeat_reward(
            db,
            order_id,
            customer_id,
            source_order_id,
        ),
        compensable=True,
    )
    return result.order


async def submit_order(db: Session, data: schemas.OrderCreate) -> schemas.OrderOut:
    """Create an order, then settle retry-safe product effects without false 500s."""
    result = create_order_result(db, data)
    response = schemas.OrderOut.model_validate(result.order)
    order_id = result.order.id
    customer_id = result.order.customer_id
    source_order_id = result.order.source_order_id
    created_at = result.order.created_at

    _run_post_commit_effect(
        db,
        result,
        "repeat_reward",
        lambda: _ensure_repeat_reward(
            db,
            order_id,
            customer_id,
            source_order_id,
        ),
        compensable=True,
    )
    if customer_id:
        _run_post_commit_effect(
            db,
            result,
            "first_meal_memory",
            lambda: _ensure_first_meal_memory(
                db,
                order_id,
                customer_id,
                created_at,
            ),
            compensable=True,
        )
    _run_post_commit_effect(
        db,
        result,
        "order_created_notification",
        lambda: _ensure_order_created_notification(db, order_id),
        compensable=True,
    )

    if result.created:
        try:
            await order_event_hub.broadcast("order_created", order_id)
        except Exception:
            logger.exception(
                "order_post_commit_effect_failed effect=order_created_broadcast "
                "order_id=%s created=true compensable=false",
                order_id,
            )
    return response


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


def latest_customer_order(db: Session, customer_id: str) -> models.Order | None:
    """Return the newest order without loading the customer's full history."""
    return orders_repository.latest_customer(db, customer_id)


def _get_order_for_status_write(db: Session, order_id: int) -> models.Order:
    """Lock one order row before status comparison and mutation."""
    order = orders_repository.find_for_update(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


def _status_business_date(value: datetime | None) -> date:
    """Map a stored UTC status timestamp to its China business date."""
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone(timedelta(hours=8))).date()


def _update_order_status_result(
    db: Session,
    order_id: int,
    status: str,
    actor_id: str,
    expected_status: str | None,
) -> OrderStatusMutationResult:
    """Commit one locked forward transition or identify an idempotent replay."""
    order = _get_order_for_status_write(db, order_id)
    previous = order.status
    if status == previous:
        return OrderStatusMutationResult(order, False, previous)
    if expected_status is not None and expected_status != previous:
        raise HTTPException(
            status_code=409,
            detail=(
                f"订单状态已变化：操作时为“{expected_status}”，"
                f"现在为“{previous}”，请刷新后重试"
            ),
        )
    if status not in ORDER_STATUS_TRANSITIONS.get(previous, set()):
        raise HTTPException(
            status_code=409,
            detail=f"订单不能从“{previous}”直接变为“{status}”",
        )
    order.status = status
    order.status_updated_at = datetime.now(timezone.utc)
    order = orders_repository.commit_status_event(
        db,
        order,
        previous,
        "ADMIN",
        actor_id,
    )
    return OrderStatusMutationResult(order, True, previous)


def _settle_status_effects(
    db: Session,
    result: OrderStatusMutationResult,
) -> None:
    """Settle independent status effects without changing the committed result."""
    order_id = result.order.id
    status = result.order.status
    customer_id = result.order.customer_id
    created_at = result.order.created_at
    completion_date = _status_business_date(result.order.status_updated_at)

    if result.changed and customer_id:
        _run_committed_order_effect(
            db,
            "status_update",
            order_id,
            "status_notification",
            lambda: notification_service.create_notification(
                db,
                customer_id,
                "ORDER_STATUS",
                f"订单 #{order_id}：{status}",
                "小厨房有新的进度，点开就能看到。",
                order_id,
            ),
            compensable=False,
        )

    if status != "已完成" or not customer_id:
        return
    _run_committed_order_effect(
        db,
        "status_update",
        order_id,
        "completion_score",
        lambda: record_score(
            db,
            customer_id,
            "ORDER_COMPLETE",
            10,
            "完成一次晚餐制作",
            order_id,
        ),
        compensable=True,
    )
    _run_committed_order_effect(
        db,
        "status_update",
        order_id,
        "first_cook_memory",
        lambda: couple_profile_service.record_first_memory(
            db,
            customer_id,
            "FIRST_COOK",
            "第一次完成专属晚餐",
            "认真准备的一顿饭，成为了我们的共同记录。",
            "ORDER_COMPLETE",
            order_id,
            created_at.date(),
        ),
        compensable=True,
    )
    _run_committed_order_effect(
        db,
        "status_update",
        order_id,
        "meal_task",
        lambda: complete_task_type(
            db,
            customer_id,
            "MEAL",
            event_date=completion_date,
        ),
        compensable=True,
    )


def update_order_status(
    db: Session,
    order_id: int,
    status: str,
    actor_id: str = "admin",
    expected_status: str | None = None,
) -> models.Order:
    """Preserve the synchronous service API with truthful best-effort effects."""
    result = _update_order_status_result(
        db,
        order_id,
        status,
        actor_id,
        expected_status,
    )
    if result.changed:
        _settle_status_effects(db, result)
    return get_order(db, order_id)


async def change_order_status(
    db: Session,
    order_id: int,
    data: schemas.OrderStatusUpdate,
    actor_id: str = "admin",
) -> schemas.OrderOut:
    """Acknowledge a committed status before isolated effects and broadcast."""
    result = _update_order_status_result(
        db,
        order_id,
        data.status,
        actor_id,
        data.expected_status,
    )
    response = schemas.OrderOut.model_validate(result.order)
    _settle_status_effects(db, result)
    if result.changed:
        try:
            await order_event_hub.broadcast("order_status_changed", order_id)
        except Exception:
            logger.exception(
                "order_committed_effect_failed operation=status_update "
                "effect=status_broadcast order_id=%s compensable=false",
                order_id,
            )
    return response


def _rollback_order_status_result(
    db: Session,
    order_id: int,
    actor_id: str,
    expected_status: str | None,
) -> OrderStatusMutationResult:
    """Commit one safe rollback or identify a legacy retry of the last rollback."""
    order = _get_order_for_status_write(db, order_id)
    previous = order.status
    latest_event = orders_repository.find_latest_status_event(db, order.id)
    if expected_status is not None and expected_status != previous:
        raise HTTPException(
            status_code=409,
            detail=(
                f"订单状态已变化：操作时为“{expected_status}”，"
                f"现在为“{previous}”，请刷新后重试"
            ),
        )
    if (
        expected_status is None
        and latest_event
        and latest_event.actor_type == "ADMIN_ROLLBACK"
    ):
        return OrderStatusMutationResult(order, False, previous)
    if previous == "已完成":
        raise HTTPException(status_code=409, detail="已完成订单禁止回退，原评价会被完整保留")
    event = orders_repository.find_latest_forward_event_for_status(
        db,
        order.id,
        previous,
    )
    if not event or not event.from_status:
        raise HTTPException(status_code=409, detail="没有可以撤回的上一步")
    order.status = event.from_status
    order.status_updated_at = datetime.now(timezone.utc)
    order = orders_repository.commit_status_event(
        db,
        order,
        previous,
        "ADMIN_ROLLBACK",
        actor_id,
    )
    return OrderStatusMutationResult(order, True, previous)


def rollback_order_status(
    db: Session,
    order_id: int,
    actor_id: str = "admin",
    expected_status: str | None = None,
) -> models.Order:
    """Preserve the synchronous rollback API with retry-safe semantics."""
    result = _rollback_order_status_result(
        db,
        order_id,
        actor_id,
        expected_status,
    )
    return result.order


async def rollback_admin_order(
    db: Session,
    order_id: int,
    data: schemas.OrderRollbackRequest | None,
    actor_id: str = "admin",
) -> schemas.OrderOut:
    """Acknowledge one committed rollback before a non-durable broadcast."""
    result = _rollback_order_status_result(
        db,
        order_id,
        actor_id,
        data.expected_status if data else None,
    )
    response = schemas.OrderOut.model_validate(result.order)
    if result.changed:
        try:
            await order_event_hub.broadcast("order_status_changed", order_id)
        except Exception:
            logger.exception(
                "order_committed_effect_failed operation=status_rollback "
                "effect=status_broadcast order_id=%s compensable=false",
                order_id,
            )
    return response
