"""Add unified users, notifications, couple archives and game recovery.

Revision ID: 20260809_08
Revises: 20260809_07
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260809_08"
down_revision: Union[str, None] = "20260809_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type():
    """Use JSONB in PostgreSQL and JSON in SQLite tests."""
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _indexes(table: str, columns: tuple[str, ...], unique: tuple[str, ...] = ()) -> None:
    """Create consistently named indexes for additive V2.7 tables."""
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column], unique=column in unique)


def upgrade() -> None:
    """Create only new V2.7 tables; existing customer codes remain valid."""
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_code", sa.String(100), nullable=False),
            sa.Column("nickname", sa.String(50), nullable=False, server_default="用户"),
            sa.Column("avatar", sa.String(500), nullable=False, server_default=""),
            sa.Column("role", sa.String(20), nullable=False, server_default="CUSTOMER"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_code"),
        )
        _indexes("users", ("id", "user_code", "role", "created_at"), ("user_code",))
    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(50), nullable=False), sa.Column("title", sa.String(100), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""), sa.Column("related_id", sa.Integer(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        )
        _indexes("notifications", ("id", "user_id", "type", "related_id", "is_read", "created_at"))
    if "couple_memories" not in tables:
        op.create_table(
            "couple_memories",
            sa.Column("id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(50), nullable=False), sa.Column("title", sa.String(100), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""), sa.Column("image_url", sa.String(500), nullable=False, server_default=""),
            sa.Column("event_date", sa.Date(), nullable=False), sa.Column("source_type", sa.String(50), nullable=True),
            sa.Column("source_id", sa.Integer(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "source_type", "source_id", name="uq_couple_memory_source"),
        )
        _indexes("couple_memories", ("id", "user_id", "type", "event_date", "source_type", "source_id", "created_at"))
    if "couple_dates" not in tables:
        op.create_table(
            "couple_dates",
            sa.Column("id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(100), nullable=False), sa.Column("date", sa.Date(), nullable=False),
            sa.Column("repeat_type", sa.String(20), nullable=False, server_default="YEARLY"),
            sa.Column("reminder_days", sa.Integer(), nullable=False, server_default=sa.text("7")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        )
        _indexes("couple_dates", ("id", "user_id", "date", "created_at"))
    if "game_reconnect_tokens" not in tables:
        op.create_table(
            "game_reconnect_tokens",
            sa.Column("id", sa.Integer(), nullable=False), sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("room_id", "user_id", name="uq_reconnect_room_user"), sa.UniqueConstraint("token_hash"),
        )
        _indexes("game_reconnect_tokens", ("id", "room_id", "user_id", "token_hash", "expires_at", "revoked", "created_at"), ("token_hash",))
    if "game_replays" not in tables:
        op.create_table(
            "game_replays",
            sa.Column("id", sa.Integer(), nullable=False), sa.Column("game_record_id", sa.Integer(), nullable=False),
            sa.Column("game_type", sa.String(50), nullable=False), sa.Column("moves", _json_type(), nullable=False),
            sa.Column("final_state", _json_type(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["game_record_id"], ["game_records.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("game_record_id"),
        )
        _indexes("game_replays", ("id", "game_record_id", "game_type", "created_at"), ("game_record_id",))


def downgrade() -> None:
    """Remove only V2.7 tables in reverse dependency order."""
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table in ("game_replays", "game_reconnect_tokens", "couple_dates", "couple_memories", "notifications", "users"):
        if table in tables:
            op.drop_table(table)
