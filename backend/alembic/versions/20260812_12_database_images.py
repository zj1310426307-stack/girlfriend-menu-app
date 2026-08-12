"""Add persistent database-backed image storage.

Revision ID: 20260812_12
Revises: 20260811_11
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_12"
down_revision: Union[str, None] = "20260811_11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "uploaded_images" in set(sa.inspect(bind).get_table_names()):
        return
    op.create_table(
        "uploaded_images",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_uploaded_images_created_at",
        "uploaded_images",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "uploaded_images" not in set(sa.inspect(bind).get_table_names()):
        return
    op.drop_index("ix_uploaded_images_created_at", table_name="uploaded_images")
    op.drop_table("uploaded_images")
