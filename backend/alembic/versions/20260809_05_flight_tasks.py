"""Add persisted flight chess, interaction events and daily couple tasks.

Revision ID: 20260809_05
Revises: 20260809_04
Create Date: 2026-08-09
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260809_05"
down_revision: Union[str, None] = "20260809_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EVENTS = (
    ("LOVE", "夸对方三个优点", 3),
    ("LOVE", "说一件最近最感谢对方的事", 3),
    ("LOVE", "回忆第一次见面时最深刻的细节", 3),
    ("FOOD", "一起决定明天最想吃的一道菜", 3),
    ("FOOD", "今天的饭后水果由你准备", 3),
    ("FOOD", "说出对方最喜欢的三道菜", 3),
    ("FUN", "模仿对方最可爱的一个小动作", 3),
    ("FUN", "给对方拍一张今天的开心照片", 3),
    ("FUN", "一起哼十秒最喜欢的歌", 3),
    ("TASK", "输的人负责洗碗", 3),
    ("TASK", "给对方一个二十秒拥抱", 3),
    ("TASK", "准备一个不花钱的小惊喜", 3),
)


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    had_game_events = "game_events" in tables

    if "game_states" not in tables:
        op.create_table(
            "game_states",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("game_type", sa.String(length=50), nullable=False),
            sa.Column("state", _json_type(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("room_id"),
        )
        op.create_index("ix_game_states_id", "game_states", ["id"])
        op.create_index("ix_game_states_room_id", "game_states", ["room_id"], unique=True)
        op.create_index("ix_game_states_game_type", "game_states", ["game_type"])
        op.create_index("ix_game_states_updated_at", "game_states", ["updated_at"])

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "game_events" not in tables:
        op.create_table(
            "game_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False, server_default=sa.text("3")),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_game_events_id", "game_events", ["id"])
        op.create_index("ix_game_events_type", "game_events", ["type"])
        op.create_index("ix_game_events_enabled", "game_events", ["enabled"])

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "game_event_logs" not in tables:
        op.create_table(
            "game_event_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.String(length=100), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False, server_default=sa.text("3")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["event_id"], ["game_events.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("id", "room_id", "event_id", "player_id", "status", "created_at", "completed_at"):
            op.create_index(f"ix_game_event_logs_{column}", "game_event_logs", [column])

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "daily_tasks" not in tables:
        op.create_table(
            "daily_tasks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=150), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False),
            sa.Column("reward_score", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("customer_id", "date", "type", name="uq_daily_task_customer_date_type"),
        )
        for column in ("id", "customer_id", "type", "status", "date", "completed_at"):
            op.create_index(f"ix_daily_tasks_{column}", "daily_tasks", [column])

    if not had_game_events:
        event_table = sa.table(
            "game_events",
            sa.column("type", sa.String()),
            sa.column("content", sa.Text()),
            sa.column("score", sa.Integer()),
            sa.column("enabled", sa.Boolean()),
            sa.column("created_at", sa.DateTime()),
        )
        op.bulk_insert(
            event_table,
            [
                {"type": kind, "content": content, "score": score, "enabled": True, "created_at": datetime.now()}
                for kind, content, score in EVENTS
            ],
        )
    if "games" in tables:
        op.execute(sa.text("UPDATE games SET status = 'available' WHERE type = 'aeroplane'"))


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "games" in tables:
        op.execute(sa.text("UPDATE games SET status = 'coming_soon' WHERE type = 'aeroplane'"))
    for table in ("daily_tasks", "game_event_logs", "game_events", "game_states"):
        if table in tables:
            op.drop_table(table)
