"""Favorite catalogue orchestration using authenticated customer identity."""

from sqlalchemy.orm import Session

import models
from repositories import favorites as favorites_repository
from services import dish_service


def list_favorite_dishes(db: Session, customer_id: str) -> list[models.Dish]:
    """List active dishes favorited by exactly one authenticated customer."""
    return favorites_repository.list_active_dishes(db, customer_id)


def add_favorite_dish(
    db: Session,
    customer_id: str,
    dish_id: int,
) -> models.Dish:
    """Idempotently favorite an active dish and return that dish as before."""
    dish = dish_service.get_dish(db, dish_id)
    if not favorites_repository.find(db, customer_id, dish_id):
        favorites_repository.add(db, customer_id, dish_id)
    return dish


def remove_favorite_dish(db: Session, customer_id: str, dish_id: int) -> None:
    """Remove an owned favorite while retaining no-op behavior when absent."""
    favorite = favorites_repository.find(db, customer_id, dish_id)
    if favorite:
        favorites_repository.remove(db, favorite)

