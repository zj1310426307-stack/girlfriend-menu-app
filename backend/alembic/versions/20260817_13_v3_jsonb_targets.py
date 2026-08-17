"""Use JSONB for the remaining extensible V3 PostgreSQL payloads.

Revision ID: 20260817_13
Revises: 20260812_12
Create Date: 2026-08-17
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260817_13"
down_revision: Union[str, None] = "20260812_12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert only generic JSON columns; SQLite already preserves JSON semantics."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE dishes ALTER COLUMN tags TYPE JSONB USING tags::jsonb"
    )
    op.execute(
        "ALTER TABLE game_records ALTER COLUMN result TYPE JSONB USING result::jsonb"
    )


def downgrade() -> None:
    """Restore PostgreSQL JSON types without deleting or rewriting payload keys."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE game_records ALTER COLUMN result TYPE JSON USING result::json"
    )
    op.execute(
        "ALTER TABLE dishes ALTER COLUMN tags TYPE JSON USING tags::json"
    )
