"""Favorite-dish persistence scoped by authenticated customer identity."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models


def list_active_dishes(db: Session, customer_id: str) -> list[models.Dish]:
    """Return one customer's active favorites in the existing newest-first order."""
    return (
        db.query(models.Dish)
        .join(models.FavoriteDish, models.FavoriteDish.dish_id == models.Dish.id)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.Dish.is_active.is_(True),
        )
        .order_by(models.FavoriteDish.created_at.desc())
        .all()
    )


def find(db: Session, customer_id: str, dish_id: int) -> models.FavoriteDish | None:
    """Find an owned favorite without applying product response semantics."""
    return (
        db.query(models.FavoriteDish)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.FavoriteDish.dish_id == dish_id,
        )
        .first()
    )


def add(db: Session, customer_id: str, dish_id: int) -> None:
    """Insert one favorite and preserve the historical race-safe commit behavior."""
    db.add(models.FavoriteDish(customer_id=customer_id, dish_id=dish_id))
    try:
        db.commit()
    except IntegrityError:
        # The database unique constraint is the final guard when two taps race.
        db.rollback()


def remove(db: Session, favorite: models.FavoriteDish) -> None:
    """Delete an existing owned favorite in the original one-commit sequence."""
    db.delete(favorite)
    db.commit()

