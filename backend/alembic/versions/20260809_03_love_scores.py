"""Add the V2.2 love score event ledger.

Revision ID: 20260809_03
Revises: 20260809_02
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260809_03"
down_revision: Union[str, None] = "20260809_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "love_scores" in inspector.get_table_names():
        return
    op.create_table(
        "love_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id",
            "type",
            "related_id",
            name="uq_love_score_source",
        ),
    )
    op.create_index("ix_love_scores_id", "love_scores", ["id"])
    op.create_index("ix_love_scores_customer_id", "love_scores", ["customer_id"])
    op.create_index("ix_love_scores_type", "love_scores", ["type"])
    op.create_index("ix_love_scores_related_id", "love_scores", ["related_id"])
    op.create_index("ix_love_scores_created_at", "love_scores", ["created_at"])


def downgrade() -> None:
    if "love_scores" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("love_scores")
