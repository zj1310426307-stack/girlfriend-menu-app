"""Order, review and order-state routes with unchanged ownership checks."""

from datetime import date
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import couple_profile_service
import crud
import notification_service
import schemas
import user_service
from api.dependencies import (
    allow_legacy_customer_header,
    get_customer_id,
    get_optional_customer_id,
    verify_admin_token,
)
from database import get_db
from realtime import order_event_hub


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/api/orders",
    response_model=schemas.OrderOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_order(
    data: schemas.OrderCreate,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    """Create an owned order and preserve notifications, memory and broadcast side effects."""
    if not customer_id and allow_legacy_customer_header() and data.customer_id:
        customer_id = data.customer_id.strip()[:100]
        logger.warning("deprecated_order_body_customer_id")
    if not customer_id:
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    order = crud.create_order(db, data.model_copy(update={"customer_id": customer_id}))
    if order.customer_id:
        user_service.ensure_user(db, order.customer_id)
        couple_profile_service.record_first_memory(
            db,
            order.customer_id,
            "FIRST_MEAL",
            "第一次在这里点菜",
            "从这一顿开始，把喜欢慢慢写进共同菜单。",
            "ORDER",
            order.id,
            order.created_at.date(),
        )
    notification_service.create_notification(
        db,
        "admin",
        "ORDER_CREATED",
        f"收到新点菜单 #{order.id}",
        "她已经选好想吃的菜，去小厨房看看吧。",
        order.id,
    )
    await order_event_hub.broadcast("order_created", order.id)
    return order


@router.post(
    "/api/orders/{order_id}/repeat-preview",
    response_model=schemas.OrderRepeatDraft,
)
def repeat_order(
    order_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return an editable repeat-order draft owned by the current customer."""
    return crud.repeat_order_draft(db, order_id, customer_id)


@router.post(
    "/api/orders/repeat/{order_id}",
    response_model=schemas.OrderRepeatDraft,
    deprecated=True,
)
def repeat_order_legacy(
    order_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Preserve the deprecated repeat-order path for deployed clients."""
    logger.warning("deprecated_endpoint endpoint=/api/orders/repeat/{order_id}")
    return crud.repeat_order_draft(db, order_id, customer_id)


@router.get(
    "/api/orders",
    response_model=list[schemas.OrderOut],
    dependencies=[Depends(verify_admin_token)],
)
def orders(db: Session = Depends(get_db)):
    """List all orders for the authenticated administrator."""
    return crud.list_orders(db)


@router.get(
    "/api/admin/orders",
    response_model=schemas.AdminOrderPage,
    dependencies=[Depends(verify_admin_token)],
)
def admin_orders(
    status: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    """Return the existing filtered cursor page for administrator order management."""
    try:
        parsed_start = date.fromisoformat(start_date) if start_date else None
        parsed_end = date.fromisoformat(end_date) if end_date else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail="日期必须使用 YYYY-MM-DD") from error
    return crud.list_admin_orders(
        db,
        status,
        cursor,
        limit,
        keyword,
        parsed_start,
        parsed_end,
    )


@router.get("/api/orders/me", response_model=list[schemas.OrderOut])
def my_orders(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """List orders owned by the authenticated customer."""
    return crud.list_customer_orders(db, customer_id)


@router.get(
    "/api/orders/my/{legacy_customer_id}",
    response_model=list[schemas.OrderOut],
    deprecated=True,
)
def legacy_my_orders(
    legacy_customer_id: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Preserve the deprecated path while preventing cross-customer access."""
    logger.warning("deprecated_endpoint endpoint=/api/orders/my/{customer_id}")
    if legacy_customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return crud.list_customer_orders(db, customer_id)


@router.get("/api/orders/{order_id}", response_model=schemas.OrderOut)
def order_detail(
    order_id: int,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    """Return one order only when the existing ownership policy allows it."""
    order = crud.get_order(db, order_id)
    if not customer_id and allow_legacy_customer_header():
        return order
    if not customer_id or order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.patch(
    "/api/orders/{order_id}/status",
    response_model=schemas.OrderOut,
    dependencies=[Depends(verify_admin_token)],
)
async def change_order_status(
    order_id: int,
    data: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update an order and preserve notification, memory and WebSocket effects."""
    previous_status = crud.get_order(db, order_id).status
    order = crud.update_order_status(db, order_id, data.status)
    if order.customer_id and previous_status != order.status:
        notification_service.create_notification(
            db,
            order.customer_id,
            "ORDER_STATUS",
            f"订单 #{order.id}：{order.status}",
            "小厨房有新的进度，点开就能看到。",
            order.id,
        )
        if order.status == "已完成":
            couple_profile_service.record_first_memory(
                db,
                order.customer_id,
                "FIRST_COOK",
                "第一次完成专属晚餐",
                "认真准备的一顿饭，成为了我们的共同记录。",
                "ORDER_COMPLETE",
                order.id,
                order.created_at.date(),
            )
    await order_event_hub.broadcast("order_status_changed", order.id)
    return order


@router.post(
    "/api/admin/orders/{order_id}/rollback",
    response_model=schemas.OrderOut,
    dependencies=[Depends(verify_admin_token)],
)
async def rollback_order_status(order_id: int, db: Session = Depends(get_db)):
    """Rollback an order through the administrator audit service and notify clients."""
    order = crud.rollback_order_status(db, order_id)
    await order_event_hub.broadcast("order_status_changed", order.id)
    return order


@router.post(
    "/api/orders/{order_id}/review",
    response_model=schemas.ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_order_review(
    order_id: int,
    data: schemas.ReviewCreate,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    """Create one owned review and preserve administrator notification and broadcast."""
    order = crud.get_order(db, order_id)
    if not customer_id and not allow_legacy_customer_header():
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    if customer_id and order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    review = crud.create_review(db, order_id, data)
    notification_service.create_notification(
        db,
        "admin",
        "ORDER_REVIEW",
        f"订单 #{order_id} 收到 {review.rating} 心评价",
        review.comment or "这顿饭已经留下新的口味反馈。",
        order_id,
    )
    await order_event_hub.broadcast("order_reviewed", order_id)
    return review


@router.get("/api/orders/{order_id}/review", response_model=schemas.ReviewOut)
def order_review(
    order_id: int,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    """Return one review only when the existing order ownership policy allows it."""
    order = crud.get_order(db, order_id)
    if not customer_id and not allow_legacy_customer_header():
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    if customer_id and order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return crud.get_review(db, order_id)
