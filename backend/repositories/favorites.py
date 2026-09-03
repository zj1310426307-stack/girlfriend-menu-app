"""Favorite-dish persistence scoped by authenticated customer identity."""

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models


@dataclass(frozen=True, slots=True)
class FavoriteRankingInputs:
    """Carry raw ranking facts without embedding presentation scoring in SQL."""

    order_rows: tuple
    repeat_counts: dict[int, int]
    favorite_ids: frozenset[int]


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


def ranking_inputs(db: Session, customer_id: str) -> FavoriteRankingInputs:
    """Load the three fact sets used by the stable favorite-ranking formula."""
    order_rows = (
        db.query(
            models.Dish.id.label("dish_id"),
            models.Dish.name.label("name"),
            func.sum(models.OrderItem.quantity).label("count"),
            func.avg(models.Review.rating).label("rating"),
        )
        .join(models.OrderItem, models.OrderItem.dish_id == models.Dish.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .outerjoin(models.Review, models.Review.order_id == models.Order.id)
        .filter(
            models.Order.customer_id == customer_id,
            models.Dish.is_active.is_(True),
        )
        .group_by(models.Dish.id, models.Dish.name)
        .all()
    )
    repeat_rows = (
        db.query(
            models.OrderItem.dish_id,
            func.count(func.distinct(models.Order.id)).label("repeat_count"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.Order.customer_id == customer_id,
            models.Order.source_order_id.is_not(None),
        )
        .group_by(models.OrderItem.dish_id)
        .all()
    )
    favorite_ids = frozenset(
        row.dish_id
        for row in db.query(models.FavoriteDish.dish_id)
        .filter(models.FavoriteDish.customer_id == customer_id)
        .all()
    )
    return FavoriteRankingInputs(
        order_rows=tuple(order_rows),
        repeat_counts={
            row.dish_id: int(row.repeat_count or 0) for row in repeat_rows
        },
        favorite_ids=favorite_ids,
    )
