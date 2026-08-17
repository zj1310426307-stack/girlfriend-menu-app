"""V3 database targets must stay additive, linear and PostgreSQL JSONB-aware."""

from pathlib import Path

from sqlalchemy.dialects import postgresql

import models


def test_extensible_game_payloads_compile_to_postgresql_jsonb() -> None:
    """Keep the V3 payload target efficient without changing SQLite test behavior."""
    dialect = postgresql.dialect()
    assert str(models.Dish.__table__.c.tags.type.compile(dialect=dialect)) == "JSONB"
    assert str(models.GameRecord.__table__.c.result.type.compile(dialect=dialect)) == "JSONB"
    assert str(models.GameSession.__table__.c.state.type.compile(dialect=dialect)) == "JSONB"
    assert str(models.GameReplay.__table__.c.final_state.type.compile(dialect=dialect)) == "JSONB"


def test_v3_jsonb_migration_is_non_destructive_and_sqlite_safe() -> None:
    """Guard the migration against table drops or unconditional vendor SQL."""
    source = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260817_13_v3_jsonb_targets.py"
    ).read_text(encoding="utf-8")
    assert 'dialect.name != "postgresql"' in source
    assert "DROP TABLE" not in source.upper()
    assert "USING tags::jsonb" in source
    assert "USING result::jsonb" in source
