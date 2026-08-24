"""Bind stable WeChat identities to existing customer sessions.

Revision ID: 20260817_14
Revises: 20260817_13
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260817_14"
down_revision = "20260817_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add identity bindings and database-owned administrator authentication."""
    op.create_table(
        "wx_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=False),
        sa.Column("unionid", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("app_id", "openid", name="uq_wx_user_app_openid"),
        sa.UniqueConstraint("customer_id"),
    )
    op.create_index("ix_wx_users_id", "wx_users", ["id"], unique=False)
    op.create_index("ix_wx_users_customer_id", "wx_users", ["customer_id"], unique=True)
    op.create_index("ix_wx_users_app_id", "wx_users", ["app_id"], unique=False)
    op.create_index("ix_wx_users_openid", "wx_users", ["openid"], unique=False)
    op.create_index("ix_wx_users_unionid", "wx_users", ["unionid"], unique=False)
    op.create_index("ix_wx_users_created_at", "wx_users", ["created_at"], unique=False)
    op.create_index("ix_wx_users_last_login_at", "wx_users", ["last_login_at"], unique=False)

    op.create_table(
        "admin_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_admin_accounts_id", "admin_accounts", ["id"], unique=False)
    op.create_index("ix_admin_accounts_username", "admin_accounts", ["username"], unique=True)
    op.create_index("ix_admin_accounts_role", "admin_accounts", ["role"], unique=False)
    op.create_index("ix_admin_accounts_is_active", "admin_accounts", ["is_active"], unique=False)
    op.create_index("ix_admin_accounts_created_at", "admin_accounts", ["created_at"], unique=False)
    op.create_index("ix_admin_accounts_last_login_at", "admin_accounts", ["last_login_at"], unique=False)

    op.create_table(
        "admin_auth_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admin_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_auth_events_id", "admin_auth_events", ["id"], unique=False)
    op.create_index("ix_admin_auth_events_admin_id", "admin_auth_events", ["admin_id"], unique=False)
    op.create_index("ix_admin_auth_events_username", "admin_auth_events", ["username"], unique=False)
    op.create_index("ix_admin_auth_events_outcome", "admin_auth_events", ["outcome"], unique=False)
    op.create_index("ix_admin_auth_events_created_at", "admin_auth_events", ["created_at"], unique=False)


def downgrade() -> None:
    """Remove only Phase 3 additive auth tables; customer history remains intact."""
    op.drop_index("ix_admin_auth_events_created_at", table_name="admin_auth_events")
    op.drop_index("ix_admin_auth_events_outcome", table_name="admin_auth_events")
    op.drop_index("ix_admin_auth_events_username", table_name="admin_auth_events")
    op.drop_index("ix_admin_auth_events_admin_id", table_name="admin_auth_events")
    op.drop_index("ix_admin_auth_events_id", table_name="admin_auth_events")
    op.drop_table("admin_auth_events")
    op.drop_index("ix_admin_accounts_last_login_at", table_name="admin_accounts")
    op.drop_index("ix_admin_accounts_created_at", table_name="admin_accounts")
    op.drop_index("ix_admin_accounts_is_active", table_name="admin_accounts")
    op.drop_index("ix_admin_accounts_role", table_name="admin_accounts")
    op.drop_index("ix_admin_accounts_username", table_name="admin_accounts")
    op.drop_index("ix_admin_accounts_id", table_name="admin_accounts")
    op.drop_table("admin_accounts")
    op.drop_index("ix_wx_users_last_login_at", table_name="wx_users")
    op.drop_index("ix_wx_users_created_at", table_name="wx_users")
    op.drop_index("ix_wx_users_unionid", table_name="wx_users")
    op.drop_index("ix_wx_users_openid", table_name="wx_users")
    op.drop_index("ix_wx_users_app_id", table_name="wx_users")
    op.drop_index("ix_wx_users_customer_id", table_name="wx_users")
    op.drop_index("ix_wx_users_id", table_name="wx_users")
    op.drop_table("wx_users")
