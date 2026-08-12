"""Alembic coverage for backfilling pre-Phase 1 customer bearer hashes."""

import sqlite3

from alembic import command
from alembic.config import Config

import database


def test_customer_session_migration_backfills_and_round_trips(tmp_path):
    db_path = tmp_path / "customer-session-migration.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    original_url = database.DATABASE_URL
    config = Config("alembic.ini")
    try:
        database.DATABASE_URL = database_url
        command.upgrade(config, "20260811_10")
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                INSERT INTO customers
                    (id, token_hash, display_name, is_active, legacy_customer_id,
                     created_at, updated_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "gf_bridge_migration",
                    "hash_bridge_migration",
                    "旧设备",
                    1,
                    "gf_old_bridge",
                    "2026-08-11T00:00:00+00:00",
                    "2026-08-11T00:00:00+00:00",
                    None,
                ),
            )
            connection.commit()

        command.upgrade(config, "head")
        with sqlite3.connect(db_path) as connection:
            row = connection.execute(
                "SELECT customer_id, token_hash, expires_at, device_label FROM customer_sessions"
            ).fetchone()
            assert row is not None
            assert row[0] == "gf_bridge_migration"
            assert row[1] == "hash_bridge_migration"
            assert row[2]
            assert row[3] == "migration-bridge"

        command.downgrade(config, "20260811_10")
        with sqlite3.connect(db_path) as connection:
            tables = {
                item[0]
                for item in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            assert "customer_sessions" not in tables
        command.upgrade(config, "head")
    finally:
        database.DATABASE_URL = original_url
