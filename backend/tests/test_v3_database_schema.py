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


def test_wechat_identity_reuses_customer_sessions_without_storing_session_key() -> None:
    """Keep WeChat as an additive identity binding, not a second session system."""
    columns = set(models.WeChatUser.__table__.columns.keys())
    assert columns == {
        "id",
        "customer_id",
        "app_id",
        "openid",
        "unionid",
        "created_at",
        "last_login_at",
    }
    assert "session_key" not in columns
    assert models.WeChatUser.__table__.c.customer_id.unique


def test_admin_authentication_persists_only_hashes_and_minimal_audit_fields() -> None:
    """Keep production admin auth database-owned without credential-bearing logs."""
    assert "password" not in models.AdminAccount.__table__.columns
    assert "password_hash" in models.AdminAccount.__table__.columns
    audit_columns = set(models.AdminAuthEvent.__table__.columns.keys())
    assert audit_columns == {"id", "admin_id", "username", "outcome", "created_at"}
