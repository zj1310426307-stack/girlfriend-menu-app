"""Read-only home bootstrap orchestration across existing domain services."""

import logging
from time import perf_counter
from typing import Callable, TypeVar

from sqlalchemy.orm import Session

import love_score
import task_service
from services import dish_service, favorite_service, order_service

logger = logging.getLogger(__name__)
BootstrapValue = TypeVar("BootstrapValue")


def _measure_read(
    stage: str,
    reader: Callable[[], BootstrapValue],
    durations_ms: dict[str, int],
) -> BootstrapValue:
    """Execute one bootstrap read and record a coarse, non-sensitive duration."""
    started_at = perf_counter()
    value = reader()
    durations_ms[stage] = round((perf_counter() - started_at) * 1000)
    return value


def build_home_bootstrap(db: Session, customer_id: str) -> dict:
    """Return only data required for the first authenticated home render."""
    started_at = perf_counter()
    durations_ms: dict[str, int] = {}
    result = {
        "dishes": _measure_read(
            "dishes", lambda: dish_service.list_dishes(db), durations_ms
        ),
        "favorite_ranking": _measure_read(
            "favorite_ranking",
            lambda: favorite_service.rank_favorite_dishes(db, customer_id),
            durations_ms,
        ),
        "couple_score": _measure_read(
            "couple_score", lambda: love_score.score_summary(db, customer_id), durations_ms
        ),
        "today_tasks": _measure_read(
            "today_tasks", lambda: task_service.today_summary(db, customer_id), durations_ms
        ),
        "recent_order": _measure_read(
            "recent_order",
            lambda: order_service.latest_customer_order(db, customer_id),
            durations_ms,
        ),
    }
    durations_ms["total"] = round((perf_counter() - started_at) * 1000)
    logger.info("home_bootstrap_ready durations_ms=%s", durations_ms)
    return result
