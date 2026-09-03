"""Security contracts for PostgreSQL backup and restore subprocesses."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backup_database.py"
SPEC = importlib.util.spec_from_file_location("backup_database", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
backup_database = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup_database)


def test_postgres_cli_keeps_password_out_of_process_arguments(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "must-not-be-inherited")
    database_url = (
        "postgresql+psycopg2://backup_user:p%40ssword@db.example:6543/"
        "restore_verify?sslmode=require&channel_binding=require"
    )

    command, environment = backup_database._postgres_cli(
        database_url,
        "pg_dump",
        "--format=custom",
    )

    assert command == [
        "pg_dump",
        "--format=custom",
        "--host",
        "db.example",
        "--port",
        "6543",
        "--username",
        "backup_user",
        "--dbname",
        "restore_verify",
    ]
    assert "p@ssword" not in " ".join(command)
    assert environment["PGPASSWORD"] == "p@ssword"
    assert environment["PGSSLMODE"] == "require"
    assert environment["PGCHANNELBINDING"] == "require"
    assert "DATABASE_URL" not in environment


def test_backup_does_not_delete_existing_backups_without_explicit_retention(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE dishes (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO dishes (id) VALUES (1)")
    existing = tmp_path / "girlfriend-menu-existing.dump"
    existing.write_bytes(b"keep me")

    created = backup_database.backup(f"sqlite:///{source.as_posix()}", tmp_path)

    assert created.exists()
    assert existing.read_bytes() == b"keep me"
