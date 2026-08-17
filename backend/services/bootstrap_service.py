"""Read-only home bootstrap orchestration across existing domain services."""

from sqlalchemy.orm import Session

import love_score
from services import dish_service, favorite_service


def build_home_bootstrap(db: Session, customer_id: str) -> dict:
    """Return only data required for the first authenticated home render."""
    return {
        "dishes": dish_service.list_dishes(db),
        "favorite_ranking": favorite_service.rank_favorite_dishes(db, customer_id),
        "couple_score": love_score.score_summary(db, customer_id),
    }
