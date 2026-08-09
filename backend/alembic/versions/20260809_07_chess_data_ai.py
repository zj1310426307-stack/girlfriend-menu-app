"""Add Chinese chess, AI catalog, rankings and private game memories.

Revision ID: 20260809_07
Revises: 20260809_06
Create Date: 2026-08-09
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260809_07"
down_revision: Union[str, None] = "20260809_06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AI_PLAYERS = (
    ("chinese_chess", "random", "象棋练习生", {"style": "random"}),
    ("chinese_chess", "rule", "象棋陪练官", {"style": "capture_check"}),
    ("jungle", "random", "森林新手", {"style": "random"}),
    ("jungle", "rule", "森林向导", {"style": "rule"}),
    ("landlord", "random", "牌桌新手", {"style": "random"}),
    ("landlord", "rule", "牌桌搭档", {"style": "rule"}),
    ("gomoku", "random", "五子棋新手", {"style": "random", "reserved": True}),
    ("gomoku", "rule", "五子棋陪练", {"style": "rule", "reserved": True}),
)

ACHIEVEMENTS = (
    ("gomoku_master_20", "五子棋达人", "累计赢得 20 局五子棋", 50, "gomoku", "wins", 20),
    ("chess_first", "楚河初遇", "完成第一局中国象棋", 10, "chinese_chess", "plays", 1),
    ("chess_couple_10", "棋逢知己", "两个人共同完成 10 局中国象棋", 50, "chinese_chess", "plays", 10),
)


def _json_type():
    """Use JSONB in PostgreSQL and JSON in SQLite tests."""
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    """Create additive V2.6 tables and publish Chinese chess in the catalog."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "chess_games" not in tables:
        op.create_table(
            "chess_games",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("round_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("red_player", sa.String(100), nullable=False),
            sa.Column("black_player", sa.String(100), nullable=True),
            sa.Column("winner", sa.String(100), nullable=True),
            sa.Column("move_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("duration", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("room_id", "round_number", name="uq_chess_game_room_round"),
        )
        for column in ("id", "room_id", "red_player", "black_player", "winner", "created_at", "finished_at"):
            op.create_index(f"ix_chess_games_{column}", "chess_games", [column])
    if "chess_moves" not in tables:
        op.create_table(
            "chess_moves",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column("move_number", sa.Integer(), nullable=False),
            sa.Column("player", sa.String(100), nullable=False),
            sa.Column("piece", sa.String(40), nullable=False),
            sa.Column("from_pos", sa.String(8), nullable=False),
            sa.Column("to_pos", sa.String(8), nullable=False),
            sa.Column("notation", sa.String(80), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["game_id"], ["chess_games.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_id", "move_number", name="uq_chess_move_game_number"),
        )
        for column in ("id", "game_id", "player", "created_at"):
            op.create_index(f"ix_chess_moves_{column}", "chess_moves", [column])
    if "ai_players" not in tables:
        op.create_table(
            "ai_players",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_type", sa.String(50), nullable=False),
            sa.Column("level", sa.String(20), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("config", _json_type(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_type", "level", name="uq_ai_player_game_level"),
        )
        for column in ("id", "game_type", "level", "enabled"):
            op.create_index(f"ix_ai_players_{column}", "ai_players", [column])
    if "game_statistics" not in tables:
        op.create_table(
            "game_statistics",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.String(100), nullable=False),
            sa.Column("game_type", sa.String(50), nullable=False),
            sa.Column("total_games", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("wins", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("losses", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("draws", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("win_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("player_id", "game_type", name="uq_game_stat_player_type"),
        )
        for column in ("id", "player_id", "game_type", "updated_at"):
            op.create_index(f"ix_game_statistics_{column}", "game_statistics", [column])
    if "game_memories" not in tables:
        op.create_table(
            "game_memories",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.String(100), nullable=False),
            sa.Column("game_type", sa.String(50), nullable=False),
            sa.Column("event", sa.String(50), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("related_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("customer_id", "game_type", "event", "related_id", name="uq_game_memory_event"),
        )
        for column in ("id", "customer_id", "game_type", "event", "related_id", "created_at"):
            op.create_index(f"ix_game_memories_{column}", "game_memories", [column])

    ai_table = sa.table("ai_players", sa.column("game_type"), sa.column("level"), sa.column("name"), sa.column("config", _json_type()), sa.column("enabled"), sa.column("created_at"))
    existing_ai = set(bind.execute(sa.text("SELECT game_type, level FROM ai_players")).fetchall())
    additions = [{"game_type": game, "level": level, "name": name, "config": config, "enabled": True, "created_at": datetime.now()} for game, level, name, config in AI_PLAYERS if (game, level) not in existing_ai]
    if additions:
        op.bulk_insert(ai_table, additions)
    if "achievements" in tables:
        achievement_table = sa.table("achievements", sa.column("code"), sa.column("name"), sa.column("description"), sa.column("reward_score"), sa.column("game_type"), sa.column("metric"), sa.column("threshold"), sa.column("enabled"), sa.column("created_at"))
        existing_codes = {row[0] for row in bind.execute(sa.text("SELECT code FROM achievements"))}
        achievement_additions = [{"code": code, "name": name, "description": description, "reward_score": reward, "game_type": game, "metric": metric, "threshold": threshold, "enabled": True, "created_at": datetime.now()} for code, name, description, reward, game, metric, threshold in ACHIEVEMENTS if code not in existing_codes]
        if achievement_additions:
            op.bulk_insert(achievement_table, achievement_additions)
    if "games" in tables:
        op.execute(sa.text("UPDATE games SET status = 'available' WHERE type = 'chinese_chess'"))


def downgrade() -> None:
    """Remove only V2.6 data tables and hide Chinese chess again."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "games" in tables:
        op.execute(sa.text("UPDATE games SET status = 'coming_soon' WHERE type = 'chinese_chess'"))
    if "achievements" in tables:
        op.execute(sa.text("DELETE FROM user_achievements WHERE achievement_id IN (SELECT id FROM achievements WHERE code IN ('gomoku_master_20','chess_first','chess_couple_10'))"))
        op.execute(sa.text("DELETE FROM achievements WHERE code IN ('gomoku_master_20','chess_first','chess_couple_10')"))
    for table in ("game_memories", "game_statistics", "ai_players", "chess_moves", "chess_games"):
        if table in tables:
            op.drop_table(table)
