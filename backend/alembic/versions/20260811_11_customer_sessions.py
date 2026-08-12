"""Add expiring and revocable customer sessions.

Revision ID: 20260811_11
Revises: 20260811_10
Create Date: 2026-08-11
"""

from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_11"
down_revision: Union[str, None] = "20260811_10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create session storage and give every legacy bearer a 90-day bridge."""
    bind = op.get_bind()
    if "customer_sessions" not in set(sa.inspect(bind).get_table_names()):
        op.create_table(
            "customer_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.String(length=100), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rotated_from_id", sa.Integer(), nullable=True),
            sa.Column("device_label", sa.String(length=100), nullable=True),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["rotated_from_id"],
                ["customer_sessions.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_customer_sessions_token_hash"),
        )
        for column in (
            "customer_id",
            "created_at",
            "last_seen_at",
            "expires_at",
            "revoked_at",
            "rotated_from_id",
        ):
            op.create_index(
                f"ix_customer_sessions_{column}",
                "customer_sessions",
                [column],
                unique=False,
            )

    customers = sa.table(
        "customers",
        sa.column("id", sa.String(100)),
        sa.column("token_hash", sa.String(128)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_seen_at", sa.DateTime(timezone=True)),
    )
    sessions = sa.table(
        "customer_sessions",
        sa.column("customer_id", sa.String(100)),
        sa.column("token_hash", sa.String(128)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_seen_at", sa.DateTime(timezone=True)),
        sa.column("expires_at", sa.DateTime(timezone=True)),
        sa.column("device_label", sa.String(100)),
    )
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=90)
    existing_hashes = set(bind.execute(sa.select(sessions.c.token_hash)).scalars())
    for row in bind.execute(
        sa.select(
            customers.c.id,
            customers.c.token_hash,
            customers.c.created_at,
            customers.c.last_seen_at,
        )
    ).mappings():
        if not row["token_hash"] or row["token_hash"] in existing_hashes:
            continue
        bind.execute(
            sessions.insert().values(
                customer_id=row["id"],
                token_hash=row["token_hash"],
                created_at=row["created_at"] or now,
                last_seen_at=row["last_seen_at"] or now,
                expires_at=expires_at,
                device_label="migration-bridge",
            )
        )


def downgrade() -> None:
    """Remove session rows while retaining the compatibility hash on customers."""
    for column in (
        "rotated_from_id",
        "revoked_at",
        "expires_at",
        "last_seen_at",
        "created_at",
        "customer_id",
    ):
        op.drop_index(f"ix_customer_sessions_{column}", table_name="customer_sessions")
    op.drop_table("customer_sessions")
