"""Review rules and post-commit reward orchestration."""

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import schemas
from love_score import record_score
from repositories import reviews as reviews_repository
from services import order_service
from task_service import complete_task_type


def get_review(db: Session, order_id: int) -> models.Review:
    """Require the order first, then return its review with legacy errors."""
    order_service.get_order(db, order_id)
    review = reviews_repository.find_by_order(db, order_id)
    if not review:
        raise HTTPException(status_code=404, detail="该订单还没有评价")
    return review


def create_review(
    db: Session,
    order_id: int,
    data: schemas.ReviewCreate,
) -> models.Review:
    """Create one completed-order review before settling five-star rewards.

    The review transaction deliberately commits before love-score and daily-task
    side effects, preserving the deployed transaction order and idempotency.
    """
    order = order_service.get_order(db, order_id)
    if order.status != "已完成":
        raise HTTPException(status_code=400, detail="订单完成后才能评价")
    if order.review:
        raise HTTPException(status_code=409, detail="该订单已经评价过了")

    try:
        review = reviews_repository.create(db, order_id, data)
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="该订单已经评价过了") from error

    if review.rating == 5 and order.customer_id:
        record_score(
            db,
            order.customer_id,
            "ORDER_REVIEW",
            5,
            "完成一次五星评价",
            order.id,
        )
        complete_task_type(db, order.customer_id, "REVIEW")
    return review
