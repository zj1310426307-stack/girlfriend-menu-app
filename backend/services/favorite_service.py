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


def rank_favorite_dishes(
    db: Session,
    customer_id: str,
    limit: int = 5,
) -> list[dict]:
    """Rank dishes using the deployed order, review, repeat and favorite formula."""
    facts = favorites_repository.ranking_inputs(db, customer_id)
    ranking = []
    for row in facts.order_rows:
        count = int(row.count or 0)
        rating = round(float(row.rating), 1) if row.rating is not None else None
        repeat_count = facts.repeat_counts.get(row.dish_id, 0)
        is_favorite = row.dish_id in facts.favorite_ids
        rating_basis = rating if rating is not None else 3.0
        score = rating_basis * count * (1 + repeat_count * 0.25)
        if is_favorite:
            score += 2
        ranking.append(
            {
                "dish_id": row.dish_id,
                "name": row.name,
                "count": count,
                "rating": rating,
                "repeat_count": repeat_count,
                "is_favorite": is_favorite,
                "score": round(score, 2),
            }
        )
    ranking.sort(key=lambda item: (item["score"], item["count"]), reverse=True)
    return ranking[: max(1, min(int(limit), 20))]
