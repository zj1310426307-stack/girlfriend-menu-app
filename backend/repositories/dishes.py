"""Dish catalogue persistence without HTTP or product orchestration."""

from sqlalchemy.orm import Session

import models
import schemas


def list_active(db: Session, category: str | None = None) -> list[models.Dish]:
    """Return active dishes in the existing newest-first catalogue order."""
    query = db.query(models.Dish).filter(models.Dish.is_active.is_(True))
    if category:
        query = query.filter(models.Dish.category == category)
    return query.order_by(models.Dish.id.desc()).all()


def find_active(db: Session, dish_id: int) -> models.Dish | None:
    """Find one active dish; service code owns the public not-found policy."""
    return (
        db.query(models.Dish)
        .filter(models.Dish.id == dish_id, models.Dish.is_active.is_(True))
        .first()
    )


def create(db: Session, data: schemas.DishCreate) -> models.Dish:
    """Insert and refresh a dish using the original single-commit sequence."""
    dish = models.Dish(**data.model_dump())
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


def update(
    db: Session,
    dish: models.Dish,
    data: schemas.DishUpdate,
) -> models.Dish:
    """Apply the complete update schema and keep one commit plus refresh."""
    for key, value in data.model_dump().items():
        setattr(dish, key, value)
    db.commit()
    db.refresh(dish)
    return dish


def disable(db: Session, dish: models.Dish) -> None:
    """Soft-delete a dish while preserving historical order-item snapshots."""
    dish.is_active = False
    db.commit()

