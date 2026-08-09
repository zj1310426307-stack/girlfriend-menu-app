"""Add persistent players and round records for the V2.3 game engine.

Revision ID: 20260809_04
Revises: 20260809_03
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260809_04"
down_revision: Union[str, None] = "20260809_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "game_rooms" in tables:
        room_columns = {
            column["name"] for column in inspector.get_columns("game_rooms")
        }
        if "finished_at" not in room_columns:
            op.add_column(
                "game_rooms",
                sa.Column("finished_at", sa.DateTime(), nullable=True),
            )
        if "ix_game_rooms_finished_at" not in _index_names("game_rooms"):
            op.create_index(
                "ix_game_rooms_finished_at",
                "game_rooms",
                ["finished_at"],
            )

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "game_players" not in tables:
        op.create_table(
            "game_players",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.String(length=100), nullable=False),
            sa.Column("seat", sa.Integer(), nullable=False),
            sa.Column(
                "score",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("joined_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["room_id"],
                ["game_rooms.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "room_id",
                "player_id",
                name="uq_game_player_room_player",
            ),
            sa.UniqueConstraint(
                "room_id",
                "seat",
                name="uq_game_player_room_seat",
            ),
        )
        op.create_index("ix_game_players_id", "game_players", ["id"])
        op.create_index("ix_game_players_room_id", "game_players", ["room_id"])
        op.create_index("ix_game_players_player_id", "game_players", ["player_id"])
        op.create_index("ix_game_players_joined_at", "game_players", ["joined_at"])

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "game_records" not in tables:
        op.create_table(
            "game_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column(
                "round_number",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column("game_type", sa.String(length=50), nullable=False),
            sa.Column("winner", sa.String(length=100), nullable=True),
            sa.Column(
                "duration",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["room_id"],
                ["game_rooms.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "room_id",
                "round_number",
                name="uq_game_record_room_round",
            ),
        )
        op.create_index("ix_game_records_id", "game_records", ["id"])
        op.create_index("ix_game_records_room_id", "game_records", ["room_id"])
        op.create_index("ix_game_records_game_type", "game_records", ["game_type"])
        op.create_index("ix_game_records_winner", "game_records", ["winner"])
        op.create_index("ix_game_records_created_at", "game_records", ["created_at"])

    if "games" in tables:
        op.execute(
            sa.text(
                "UPDATE games SET status = 'available' "
                "WHERE type = 'gomoku'"
            )
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "games" in tables:
        op.execute(
            sa.text(
                "UPDATE games SET status = 'coming_soon' "
                "WHERE type = 'gomoku'"
            )
        )
    if "game_records" in tables:
        op.drop_table("game_records")
    if "game_players" in tables:
        op.drop_table("game_players")
    if "game_rooms" in tables:
        indexes = _index_names("game_rooms")
        if "ix_game_rooms_finished_at" in indexes:
            op.drop_index("ix_game_rooms_finished_at", table_name="game_rooms")
        room_columns = {
            column["name"]
            for column in sa.inspect(op.get_bind()).get_columns("game_rooms")
        }
        if "finished_at" in room_columns:
            with op.batch_alter_table("game_rooms") as batch_op:
                batch_op.drop_column("finished_at")
