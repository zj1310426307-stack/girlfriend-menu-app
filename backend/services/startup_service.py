"""Reference-data initialization owned by deployment and local development."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import game_data_service
import user_service
from database import SessionLocal
from seed import seed_achievements, seed_dishes, seed_game_events, seed_games


logger = logging.getLogger(__name__)


def seed_reference_data() -> dict[str, float]:
    """Idempotently prepare catalogues once per deploy and report bounded timings."""
    stages: tuple[tuple[str, Callable], ...] = (
        ("dishes", seed_dishes),
        ("games", seed_games),
        ("game_events", seed_game_events),
        ("achievements", seed_achievements),
        ("ai_catalog", game_data_service.ensure_ai_catalog),
        ("system_users", user_service.seed_system_users),
    )
    durations: dict[str, float] = {}
    started = time.perf_counter()
    with SessionLocal() as db:
        for name, seed in stages:
            stage_started = time.perf_counter()
            seed(db)
            durations[name] = round((time.perf_counter() - stage_started) * 1000, 1)
    durations["total"] = round((time.perf_counter() - started) * 1000, 1)
    logger.info("reference_data_ready durations_ms=%s", durations)
    return durations
