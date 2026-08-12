"""Dish catalogue policies independent from HTTP transport and SQL queries."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from repositories import dishes as dishes_repository


def list_dishes(db: Session, category: str | None = None) -> list[models.Dish]:
    """List active catalogue items with the established optional category filter."""
    return dishes_repository.list_active(db, category)


def get_dish(db: Session, dish_id: int) -> models.Dish:
    """Return one active dish or preserve the established 404 response."""
    dish = dishes_repository.find_active(db, dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")
    return dish


def create_dish(db: Session, data: schemas.DishCreate) -> models.Dish:
    """Create one administrator-managed dish without extra transaction boundaries."""
    return dishes_repository.create(db, data)


def update_dish(
    db: Session,
    dish_id: int,
    data: schemas.DishUpdate,
) -> models.Dish:
    """Require an active dish, then persist the complete update payload."""
    return dishes_repository.update(db, get_dish(db, dish_id), data)


def delete_dish(db: Session, dish_id: int) -> None:
    """Disable one active dish so historical order-item snapshots remain intact."""
    dishes_repository.disable(db, get_dish(db, dish_id))

