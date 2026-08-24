"""Prepare a managed database with a minimal fast path for free-tier wakeups."""

from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine


logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_SCHEMA_HEAD = "20260817_14"
MINIMUM_REFERENCE_COUNTS = {
    "dishes": 19,
    "games": 6,
    "game_events": 12,
    "achievements": 8,
    "ai_players": 14,
    "system_users": 4,
}
RUNTIME_STATE_QUERY = text(
    """
    SELECT
        (SELECT version_num FROM alembic_version LIMIT 1) AS schema_head,
        (SELECT COUNT(*) FROM dishes) AS dishes,
        (SELECT COUNT(*) FROM games) AS games,
        (SELECT COUNT(*) FROM game_events) AS game_events,
        (SELECT COUNT(*) FROM achievements) AS achievements,
        (SELECT COUNT(*) FROM ai_players) AS ai_players,
        (
            SELECT COUNT(*) FROM users
            WHERE user_code IN ('admin', 'ai_landlord', 'ai_animal', 'ai_chess')
        ) AS system_users
    """
)


def _read_runtime_state() -> dict:
    """Read schema and bounded catalogue counts in one database round trip."""
    try:
        with engine.connect() as connection:
            row = connection.execute(RUNTIME_STATE_QUERY).mappings().one()
    except SQLAlchemyError:
        # A missing version or catalogue table is expected on the first deploy.
        return {"schema_head": "", "reference_data_ready": False, "counts": {}}
    counts = {
        name: int(row[name] or 0)
        for name in MINIMUM_REFERENCE_COUNTS
    }
    ready = all(
        counts[name] >= minimum
        for name, minimum in MINIMUM_REFERENCE_COUNTS.items()
    )
    return {
        "schema_head": str(row["schema_head"] or ""),
        "reference_data_ready": ready,
        "counts": counts,
    }


def _upgrade_schema() -> None:
    """Run Alembic lazily only when the single-query fast path finds drift."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


def _seed_reference_data() -> dict[str, float]:
    """Import the heavier catalogue graph only when reference data needs repair."""
    from services.startup_service import seed_reference_data

    return seed_reference_data()


def prepare_free_runtime() -> dict:
    """Upgrade or repair once, while keeping ordinary free-tier wakes lightweight."""
    started_at = perf_counter()
    state = _read_runtime_state()
    schema_changed = state["schema_head"] != EXPECTED_SCHEMA_HEAD
    reference_data_seeded = schema_changed or not state["reference_data_ready"]

    if schema_changed:
        _upgrade_schema()
    seed_durations = _seed_reference_data() if reference_data_seeded else {}

    if schema_changed or reference_data_seeded:
        verified = _read_runtime_state()
        if (
            verified["schema_head"] != EXPECTED_SCHEMA_HEAD
            or not verified["reference_data_ready"]
        ):
            raise RuntimeError("managed database preparation did not reach the release baseline")

    result = {
        "schema_changed": schema_changed,
        "reference_data_seeded": reference_data_seeded,
        "seed_durations_ms": seed_durations,
        "total_ms": round((perf_counter() - started_at) * 1000, 1),
    }
    logger.info(
        "free_runtime_ready schema_changed=%s reference_data_seeded=%s total_ms=%s",
        schema_changed,
        reference_data_seeded,
        result["total_ms"],
    )
    return result
