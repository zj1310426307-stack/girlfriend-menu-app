"""Review rules and truthful post-commit product orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import notification_service
import schemas
from love_score import record_score
from realtime_events import order_event_hub
from repositories import reviews as reviews_repository
from services import order_service
from task_service import complete_task_type


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewCreationResult:
    """Expose whether persistence created a review or replayed the same payload."""

    review: models.Review
    created: bool
    customer_id: str | None


def get_review(db: Session, order_id: int) -> models.Review:
    """Require the order first, then return its review with legacy errors."""
    order_service.get_order(db, order_id)
    review = reviews_repository.find_by_order(db, order_id)
    if not review:
        raise HTTPException(status_code=404, detail="该订单还没有评价")
    return review


def _matches_review(review: models.Review, data: schemas.ReviewCreate) -> bool:
    """Return whether a retry carries exactly the already-committed review."""
    return (
        review.rating == data.rating
        and review.want_again == data.want_again
        and review.comment == data.comment
    )


def _existing_review_result(
    review: models.Review,
    data: schemas.ReviewCreate,
    customer_id: str | None,
) -> ReviewCreationResult:
    """Accept an exact replay while preserving conflicts for changed feedback."""
    if not _matches_review(review, data):
        raise HTTPException(status_code=409, detail="该订单已经评价过了")
    return ReviewCreationResult(review, False, customer_id)


def create_review_result(
    db: Session,
    order_id: int,
    data: schemas.ReviewCreate,
) -> ReviewCreationResult:
    """Commit one review or return an exact natural-key replay."""
    order = order_service.get_order(db, order_id)
    if order.status != "已完成":
        raise HTTPException(status_code=400, detail="订单完成后才能评价")
    if order.review:
        return _existing_review_result(order.review, data, order.customer_id)

    try:
        review = reviews_repository.create(db, order_id, data)
    except IntegrityError as error:
        existing = reviews_repository.find_by_order(db, order_id)
        if not existing:
            raise HTTPException(
                status_code=409,
                detail="该订单已经评价过了",
            ) from error
        try:
            return _existing_review_result(existing, data, order.customer_id)
        except HTTPException as conflict:
            raise conflict from error
    return ReviewCreationResult(review, True, order.customer_id)


def _run_committed_review_effect(
    db: Session,
    order_id: int,
    effect_name: str,
    effect: Callable[[], object],
    *,
    compensable: bool,
) -> bool:
    """Isolate one optional effect from an already-committed review result."""
    try:
        effect()
        return True
    except Exception:
        logger.exception(
            "review_committed_effect_failed effect=%s order_id=%s compensable=%s",
            effect_name,
            order_id,
            str(compensable).lower(),
        )
        try:
            db.rollback()
        except Exception:
            logger.exception(
                "review_committed_effect_rollback_failed effect=%s order_id=%s",
                effect_name,
                order_id,
            )
        return False


def _review_business_date(value: datetime | None) -> date:
    """Map a stored naive-or-aware UTC review timestamp to China business date."""
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone(timedelta(hours=8))).date()


def _settle_review_effects(
    db: Session,
    result: ReviewCreationResult,
) -> None:
    """Ensure retry-safe review rewards and the durable administrator notice."""
    order_id = result.review.order_id
    rating = result.review.rating
    comment = result.review.comment
    event_date = _review_business_date(result.review.created_at)
    customer_id = result.customer_id

    if rating == 5 and customer_id:
        _run_committed_review_effect(
            db,
            order_id,
            "review_score",
            lambda: record_score(
                db,
                customer_id,
                "ORDER_REVIEW",
                5,
                "完成一次五星评价",
                order_id,
            ),
            compensable=True,
        )
        _run_committed_review_effect(
            db,
            order_id,
            "review_task",
            lambda: complete_task_type(
                db,
                customer_id,
                "REVIEW",
                event_date=event_date,
            ),
            compensable=True,
        )
    _run_committed_review_effect(
        db,
        order_id,
        "review_notification",
        lambda: notification_service.create_notification_once(
            db,
            "admin",
            "ORDER_REVIEW",
            f"订单 #{order_id} 收到 {rating} 心评价",
            comment or "这顿饭已经留下新的口味反馈。",
            order_id,
        ),
        compensable=True,
    )


def create_review(
    db: Session,
    order_id: int,
    data: schemas.ReviewCreate,
) -> models.Review:
    """Preserve the synchronous API with idempotent best-effort effects."""
    result = create_review_result(db, order_id, data)
    _settle_review_effects(db, result)
    return reviews_repository.find_by_order(db, order_id) or result.review


async def submit_review(
    db: Session,
    order_id: int,
    data: schemas.ReviewCreate,
) -> schemas.ReviewOut:
    """Acknowledge a committed review before isolated effects and broadcast."""
    result = create_review_result(db, order_id, data)
    response = schemas.ReviewOut.model_validate(result.review)
    _settle_review_effects(db, result)
    if result.created:
        try:
            await order_event_hub.broadcast("order_reviewed", order_id)
        except Exception:
            logger.exception(
                "review_committed_effect_failed effect=review_broadcast "
                "order_id=%s compensable=false",
                order_id,
            )
    return response
