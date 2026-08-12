"""Review persistence isolated from ownership and reward orchestration."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import schemas


def find_by_order(db: Session, order_id: int) -> models.Review | None:
    """Return the single review associated with an order, when it exists."""
    return (
        db.query(models.Review)
        .filter(models.Review.order_id == order_id)
        .first()
    )


def create(
    db: Session,
    order_id: int,
    data: schemas.ReviewCreate,
) -> models.Review:
    """Persist one review and roll back a racing unique-constraint failure.

    The service maps ``IntegrityError`` to the established HTTP 409 response;
    this repository owns only the database transaction cleanup.
    """
    review = models.Review(order_id=order_id, **data.model_dump())
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(review)
    return review
