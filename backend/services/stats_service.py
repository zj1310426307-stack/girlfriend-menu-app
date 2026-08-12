"""Stable service facade for non-game order statistics."""

from sqlalchemy.orm import Session

import models
from repositories import stats as stats_repository


def get_stats_summary(db: Session) -> dict:
    """Return the deployed order summary without changing its response shape."""
    return stats_repository.summary(db)


def get_dish_stats(db: Session) -> list[dict]:
    """Return per-snapshot dish totals in quantity and recency order."""
    return stats_repository.dishes(db)


def get_recent_orders(db: Session) -> list[models.Order]:
    """Return the existing ten-order recent slice."""
    return stats_repository.recent_orders(db)
