"""V2.8 authenticated devices, order audit timestamps and room sessions.

Revision ID: 20260809_09
Revises: 20260809_08
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260809_09"
down_revision: Union[str, None] = "20260809_08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "customers" not in tables:
        op.create_table(
            "customers",
            sa.Column("id", sa.String(100), nullable=False),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("display_name", sa.String(50), nullable=False, server_default="女朋友"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("legacy_customer_id", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
            sa.UniqueConstraint("legacy_customer_id"),
        )
        for column in ("token_hash", "is_active", "legacy_customer_id", "created_at", "last_seen_at"):
            op.create_index(f"ix_customers_{column}", "customers", [column], unique=column in {"token_hash", "legacy_customer_id"})

    inspector = sa.inspect(bind)
    if "orders" in tables:
        for name, type_ in (
            ("desired_at", sa.DateTime(timezone=True)),
            ("status_updated_at", sa.DateTime(timezone=True)),
            ("idempotency_key", sa.String(100)),
        ):
            if not _has_column(inspector, "orders", name):
                op.add_column("orders", sa.Column(name, type_, nullable=True))
        op.execute(sa.text("UPDATE orders SET status_updated_at = COALESCE(status_updated_at, created_at)"))
        for column, unique in (("desired_at", False), ("status_updated_at", False), ("idempotency_key", True)):
            op.create_index(f"ix_orders_{column}", "orders", [column], unique=unique)

    if "order_status_events" not in tables:
        op.create_table(
            "order_status_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("from_status", sa.String(20), nullable=True),
            sa.Column("to_status", sa.String(20), nullable=False),
            sa.Column("actor_type", sa.String(20), nullable=False, server_default="ADMIN"),
            sa.Column("actor_id", sa.String(100), nullable=False, server_default="admin"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("id", "order_id", "to_status", "created_at"):
            op.create_index(f"ix_order_status_events_{column}", "order_status_events", [column])

    inspector = sa.inspect(bind)
    if "game_rooms" in tables:
        additions = (
            ("last_activity_at", sa.DateTime(timezone=True)),
            ("expires_at", sa.DateTime(timezone=True)),
            ("state_version", sa.Integer()),
        )
        for name, type_ in additions:
            if not _has_column(inspector, "game_rooms", name):
                op.add_column("game_rooms", sa.Column(name, type_, nullable=True))
        op.execute(sa.text("UPDATE game_rooms SET last_activity_at = COALESCE(last_activity_at, created_at), state_version = COALESCE(state_version, 1)"))
        op.create_index("ix_game_rooms_last_activity_at", "game_rooms", ["last_activity_at"])
        op.create_index("ix_game_rooms_expires_at", "game_rooms", ["expires_at"])

    inspector = sa.inspect(bind)
    if "game_players" in tables:
        additions = (
            ("room_session_token_hash", sa.String(128)),
            ("last_activity_at", sa.DateTime(timezone=True)),
            ("disconnected_at", sa.DateTime(timezone=True)),
            ("expires_at", sa.DateTime(timezone=True)),
        )
        for name, type_ in additions:
            if not _has_column(inspector, "game_players", name):
                op.add_column("game_players", sa.Column(name, type_, nullable=True))
        op.execute(sa.text("UPDATE game_players SET last_activity_at = COALESCE(last_activity_at, joined_at)"))
        for column, unique in (
            ("room_session_token_hash", True),
            ("last_activity_at", False),
            ("disconnected_at", False),
            ("expires_at", False),
        ):
            op.create_index(f"ix_game_players_{column}", "game_players", [column], unique=unique)


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "game_players" in tables:
        for column in ("expires_at", "disconnected_at", "last_activity_at", "room_session_token_hash"):
            op.drop_index(f"ix_game_players_{column}", table_name="game_players")
            op.drop_column("game_players", column)
    if "game_rooms" in tables:
        op.drop_index("ix_game_rooms_expires_at", table_name="game_rooms")
        op.drop_index("ix_game_rooms_last_activity_at", table_name="game_rooms")
        for column in ("state_version", "expires_at", "last_activity_at"):
            op.drop_column("game_rooms", column)
    if "order_status_events" in tables:
        op.drop_table("order_status_events")
    if "orders" in tables:
        for column in ("idempotency_key", "status_updated_at", "desired_at"):
            op.drop_index(f"ix_orders_{column}", table_name="orders")
            op.drop_column("orders", column)
    if "customers" in tables:
        op.drop_table("customers")
