"""Render the SQLAlchemy V3 metadata as a deterministic PostgreSQL DDL snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
TARGET = ROOT / "database" / "v3-schema.sql"
sys.path.insert(0, str(BACKEND))

from database import Base  # noqa: E402
import models  # noqa: E402, F401


def _clean_ddl(statement: object) -> str:
    """Normalize SQLAlchemy's pretty DDL without committing trailing spaces."""
    return "\n".join(line.rstrip() for line in str(statement).strip().splitlines())


def render_schema() -> str:
    """Compile all current tables and indexes for the PostgreSQL production target."""
    dialect = postgresql.dialect()
    statements = [
        "-- LoveOS V3 PostgreSQL schema snapshot",
        "-- Generated from backend/models.py; Alembic remains the migration authority.",
        "-- Alembic head: 20260817_13",
        "-- Regenerate/check with: python scripts/export_v3_schema.py --check",
        "",
    ]
    for table in Base.metadata.sorted_tables:
        statements.append(_clean_ddl(CreateTable(table).compile(dialect=dialect)) + ";")
        statements.append("")
    for table in Base.metadata.sorted_tables:
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            statements.append(_clean_ddl(CreateIndex(index).compile(dialect=dialect)) + ";")
    return "\n".join(statements).rstrip() + "\n"


def main() -> int:
    """Print the snapshot or verify the committed artifact without mutating it."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_schema()
    if not args.check:
        sys.stdout.write(rendered)
        return 0
    if not TARGET.exists():
        print(f"missing schema snapshot: {TARGET}", file=sys.stderr)
        return 1
    current = TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")
    if current != rendered:
        print("database/v3-schema.sql is out of date", file=sys.stderr)
        return 1
    print("database/v3-schema.sql is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
