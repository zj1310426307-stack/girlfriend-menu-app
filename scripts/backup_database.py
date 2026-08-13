"""Create a timestamped SQLite or PostgreSQL backup plus a count manifest."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CORE_TABLES = (
    "dishes",
    "orders",
    "order_items",
    "order_status_events",
    "reviews",
    "favorite_dishes",
    "customers",
    "love_scores",
    "daily_tasks",
    "users",
    "notifications",
    "couple_memories",
    "couple_dates",
    "game_rooms",
    "game_players",
    "game_records",
    "game_states",
    "game_sessions",
    "game_replays",
)


def _url() -> str:
    load_dotenv(BACKEND / ".env")
    return os.getenv("DATABASE_URL", f"sqlite:///{BACKEND / 'girlfriend_menu.db'}")


def _counts(database_url: str) -> dict[str, int]:
    normalized_url = database_url
    if database_url.startswith("sqlite"):
        normalized_url = f"sqlite:///{_sqlite_path(database_url).as_posix()}"
    engine = create_engine(normalized_url, pool_pre_ping=True)
    try:
        existing = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            return {
                table: int(connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)
                for table in CORE_TABLES if table in existing
            }
    finally:
        engine.dispose()


def _sqlite_path(database_url: str) -> Path:
    raw = database_url.removeprefix("sqlite:///")
    path = Path(raw)
    return path if path.is_absolute() else (BACKEND / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(database_url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if database_url.startswith("sqlite"):
        source_path = _sqlite_path(database_url)
        if not source_path.exists():
            raise SystemExit(f"SQLite database does not exist: {source_path}")
        destination = output_dir / f"girlfriend-menu-{stamp}.sqlite3"
        with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
    else:
        destination = output_dir / f"girlfriend-menu-{stamp}.dump"
        subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-acl", f"--file={destination}", database_url],
            check=True,
        )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database_kind": "sqlite" if database_url.startswith("sqlite") else "postgresql",
        "backup_file": destination.name,
        "sha256": _sha256(destination),
        "counts": _counts(database_url),
    }
    destination.with_suffix(destination.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    cutoff = datetime.now(timezone.utc).timestamp() - 14 * 86400
    for candidate in output_dir.glob("girlfriend-menu-*"):
        if candidate.stat().st_mtime < cutoff:
            candidate.unlink(missing_ok=True)
    print(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "backups")
    args = parser.parse_args()
    backup(args.database_url or _url(), args.output_dir.resolve())
