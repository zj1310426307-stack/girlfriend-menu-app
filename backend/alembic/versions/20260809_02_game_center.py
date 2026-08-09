"""Add the unified V2.1 game catalog and room metadata.

Revision ID: 20260809_02
Revises: 20260808_01
Create Date: 2026-08-09
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260809_02"
down_revision: Union[str, None] = "20260808_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GAME_CATALOG = [
    {"name": "大话骰", "icon": "骰", "type": "dice", "status": "available"},
    {"name": "五子棋", "icon": "棋", "type": "gomoku", "status": "coming_soon"},
    {"name": "飞行棋", "icon": "飞", "type": "aeroplane", "status": "coming_soon"},
    {"name": "斗地主", "icon": "牌", "type": "landlord", "status": "coming_soon"},
    {"name": "斗兽棋", "icon": "兽", "type": "jungle", "status": "coming_soon"},
    {"name": "中国象棋", "icon": "象", "type": "chinese_chess", "status": "coming_soon"},
]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "games" not in tables:
        games = op.create_table(
            "games",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("icon", sa.String(length=20), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("type"),
        )
        op.create_index("ix_games_id", "games", ["id"])
        op.create_index("ix_games_type", "games", ["type"], unique=True)
        op.create_index("ix_games_status", "games", ["status"])
        op.bulk_insert(
            games,
            [{**game, "created_at": datetime.now()} for game in GAME_CATALOG],
        )

    inspector = sa.inspect(op.get_bind())
    if "game_rooms" not in inspector.get_table_names():
        op.create_table(
            "game_rooms",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_code", sa.String(length=12), nullable=False),
            sa.Column("game_type", sa.String(length=50), nullable=False),
            sa.Column("creator", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("max_players", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("room_code"),
        )
        op.create_index("ix_game_rooms_id", "game_rooms", ["id"])
        op.create_index("ix_game_rooms_room_code", "game_rooms", ["room_code"], unique=True)
        op.create_index("ix_game_rooms_game_type", "game_rooms", ["game_type"])
        op.create_index("ix_game_rooms_creator", "game_rooms", ["creator"])
        op.create_index("ix_game_rooms_status", "game_rooms", ["status"])
        op.create_index("ix_game_rooms_created_at", "game_rooms", ["created_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "game_rooms" in tables:
        op.drop_table("game_rooms")
    if "games" in tables:
        op.drop_table("games")
