"""Add durable leases, settlement receipts and idempotent game actions.

Revision ID: 20260811_10
Revises: 20260809_09
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260811_10"
down_revision: Union[str, None] = "20260809_09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type():
    """Use JSONB in PostgreSQL while keeping SQLite migration tests portable."""
    return sa.JSON().with_variant(
        postgresql.JSONB(astext_type=sa.Text()),
        "postgresql",
    )


def _has_column(inspector, table: str, column: str) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def _has_index(bind, table: str, index: str) -> bool:
    inspector = sa.inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table)}
    constraints = {
        item["name"]
        for item in inspector.get_unique_constraints(table)
        if item.get("name")
    }
    return index in indexes or index in constraints


def _create_index(bind, name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    if not _has_index(bind, table, name):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    """Apply additive stability fields without rebuilding any existing game data."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "game_rooms" in tables:
        for name, column_type, default in (
            ("owner_instance_id", sa.String(120), None),
            ("lease_expires_at", sa.DateTime(timezone=True), None),
            ("lease_epoch", sa.Integer(), "0"),
            ("abandoned_at", sa.DateTime(timezone=True), None),
        ):
            if not _has_column(inspector, "game_rooms", name):
                op.add_column(
                    "game_rooms",
                    sa.Column(
                        name,
                        column_type,
                        nullable=default is None,
                        server_default=sa.text(default) if default is not None else None,
                    ),
                )
        for column in ("owner_instance_id", "lease_expires_at", "abandoned_at"):
            _create_index(bind, f"ix_game_rooms_{column}", "game_rooms", [column])

    inspector = sa.inspect(bind)
    if "game_records" in tables:
        additions = (
            ("settlement_status", sa.String(20), "'complete'"),
            ("settlement_attempts", sa.Integer(), "0"),
            ("settlement_error", sa.Text(), None),
            ("settled_at", sa.DateTime(timezone=True), None),
        )
        for name, column_type, default in additions:
            if not _has_column(inspector, "game_records", name):
                op.add_column(
                    "game_records",
                    sa.Column(
                        name,
                        column_type,
                        nullable=default is None,
                        server_default=sa.text(default) if default is not None else None,
                    ),
                )
        op.execute(
            sa.text(
                "UPDATE game_records SET settled_at = COALESCE(settled_at, created_at) "
                "WHERE settlement_status = 'complete'"
            )
        )
        _create_index(bind, "ix_game_records_settlement_status", "game_records", ["settlement_status"])
        _create_index(bind, "ix_game_records_settled_at", "game_records", ["settled_at"])

    if "game_actions" not in tables:
        op.create_table(
            "game_actions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.String(100), nullable=False),
            sa.Column("client_action_id", sa.String(80), nullable=False),
            sa.Column("action_type", sa.String(40), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("request_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("response_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("response_state", _json_type(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "room_id",
                "player_id",
                "client_action_id",
                name="uq_game_action_room_player_client",
            ),
        )
        for column in (
            "id",
            "room_id",
            "player_id",
            "client_action_id",
            "action_type",
            "created_at",
        ):
            _create_index(bind, f"ix_game_actions_{column}", "game_actions", [column])


def downgrade() -> None:
    """Remove only V2.10 stability metadata, leaving prior game history intact."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "game_actions" in tables:
        op.drop_table("game_actions")
    if "game_records" in tables:
        for column in ("settled_at", "settlement_status"):
            index = f"ix_game_records_{column}"
            if _has_index(bind, "game_records", index):
                op.drop_index(index, table_name="game_records")
        for column in (
            "settled_at",
            "settlement_error",
            "settlement_attempts",
            "settlement_status",
        ):
            op.drop_column("game_records", column)
    if "game_rooms" in tables:
        for column in ("abandoned_at", "lease_expires_at", "owner_instance_id"):
            index = f"ix_game_rooms_{column}"
            if _has_index(bind, "game_rooms", index):
                op.drop_index(index, table_name="game_rooms")
        for column in (
            "abandoned_at",
            "lease_epoch",
            "lease_expires_at",
            "owner_instance_id",
        ):
            op.drop_column("game_rooms", column)
