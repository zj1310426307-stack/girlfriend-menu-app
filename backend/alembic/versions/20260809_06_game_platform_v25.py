"""Add V2.5 versioned game sessions, achievements and post-game tasks.

Revision ID: 20260809_06
Revises: 20260809_05
Create Date: 2026-08-09
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260809_06"
down_revision: Union[str, None] = "20260809_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACHIEVEMENTS = (
    ("first_game", "第一次并肩", "完成第一局游戏", 5, None, "plays", 1),
    ("gomoku_master", "五子棋高手", "赢得 10 局五子棋", 50, "gomoku", "wins", 10),
    ("game_couple", "游戏情侣", "共同完成 50 局游戏", 100, None, "plays", 50),
    ("landlord_rookie", "牌桌初胜", "赢得第一局斗地主", 10, "landlord", "wins", 1),
    ("jungle_explorer", "森林搭档", "完成第一局斗兽棋", 10, "jungle", "plays", 1),
)


def _json_type():
    """Use JSONB in PostgreSQL while preserving SQLite test support."""
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    """Create additive V2.5 tables without changing existing game data."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "game_sessions" not in tables:
        op.create_table(
            "game_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("game_type", sa.String(length=50), nullable=False),
            sa.Column("current_turn", sa.String(length=100), nullable=True),
            sa.Column("state", _json_type(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("room_id"),
        )
        for column in ("id", "game_type", "current_turn", "updated_at"):
            op.create_index(f"ix_game_sessions_{column}", "game_sessions", [column])
        op.create_index("ix_game_sessions_room_id", "game_sessions", ["room_id"], unique=True)

    if "achievements" not in tables:
        op.create_table(
            "achievements",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("reward_score", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("game_type", sa.String(length=50), nullable=True),
            sa.Column("metric", sa.String(length=50), nullable=False, server_default="plays"),
            sa.Column("threshold", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        for column in ("id", "code", "game_type", "enabled"):
            op.create_index(
                f"ix_achievements_{column}", "achievements", [column], unique=column == "code"
            )

    if "user_achievements" not in tables:
        op.create_table(
            "user_achievements",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.String(length=100), nullable=False),
            sa.Column("achievement_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "customer_id",
                "achievement_id",
                name="uq_user_achievement_customer_definition",
            ),
        )
        for column in ("id", "customer_id", "achievement_id", "created_at"):
            op.create_index(f"ix_user_achievements_{column}", "user_achievements", [column])

    if "love_tasks" not in tables:
        op.create_table(
            "love_tasks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_record_id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["game_record_id"], ["game_records.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_record_id", "player_id", name="uq_love_task_record_player"),
        )
        for column in ("id", "game_record_id", "player_id", "status", "created_at", "completed_at"):
            op.create_index(f"ix_love_tasks_{column}", "love_tasks", [column])

    achievement_table = sa.table(
        "achievements",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("reward_score", sa.Integer()),
        sa.column("game_type", sa.String()),
        sa.column("metric", sa.String()),
        sa.column("threshold", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
    )
    existing = {code for (code,) in bind.execute(sa.text("SELECT code FROM achievements"))}
    additions = [
            {
                "code": code,
                "name": name,
                "description": description,
                "reward_score": reward,
                "game_type": game_type,
                "metric": metric,
                "threshold": threshold,
                "enabled": True,
                "created_at": datetime.now(),
            }
            for code, name, description, reward, game_type, metric, threshold in ACHIEVEMENTS
            if code not in existing
        ]
    if additions:
        op.bulk_insert(achievement_table, additions)
    if "games" in tables:
        op.execute(
            sa.text("UPDATE games SET status = 'available' WHERE type IN ('landlord', 'jungle')")
        )


def downgrade() -> None:
    """Remove only V2.5 tables and restore catalog visibility."""
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "games" in tables:
        op.execute(
            sa.text("UPDATE games SET status = 'coming_soon' WHERE type IN ('landlord', 'jungle')")
        )
    for table in ("love_tasks", "user_achievements", "achievements", "game_sessions"):
        if table in tables:
            op.drop_table(table)
