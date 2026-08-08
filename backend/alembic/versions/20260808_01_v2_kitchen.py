"""Add V2 favorites, repeat orders and dish metadata.

Revision ID: 20260808_01
Revises:
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260808_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "dishes" not in tables:
        op.create_table(
            "dishes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("image_url", sa.String(length=500), nullable=True),
            sa.Column("cook_time", sa.Integer(), nullable=True),
            sa.Column("difficulty", sa.Integer(), nullable=True),
            sa.Column("spicy_level", sa.Integer(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_dishes_id", "dishes", ["id"])
        op.create_index("ix_dishes_category", "dishes", ["category"])
        op.create_index("ix_dishes_is_active", "dishes", ["is_active"])
    else:
        columns = _columns(inspector, "dishes")
        for column in (
            sa.Column("cook_time", sa.Integer(), nullable=True),
            sa.Column("difficulty", sa.Integer(), nullable=True),
            sa.Column("spicy_level", sa.Integer(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
        ):
            if column.name not in columns:
                op.add_column("dishes", column)

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "orders" not in tables:
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("desired_time", sa.String(length=50), nullable=True),
            sa.Column("customer_id", sa.String(length=100), nullable=True),
            sa.Column("source_order_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["source_order_id"], ["orders.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for name, columns in (
            ("ix_orders_id", ["id"]),
            ("ix_orders_status", ["status"]),
            ("ix_orders_customer_id", ["customer_id"]),
            ("ix_orders_source_order_id", ["source_order_id"]),
            ("ix_orders_created_at", ["created_at"]),
        ):
            op.create_index(name, "orders", columns)
    else:
        columns = _columns(inspector, "orders")
        if "source_order_id" not in columns:
            op.add_column("orders", sa.Column("source_order_id", sa.Integer(), nullable=True))
        inspector = sa.inspect(bind)
        if "ix_orders_source_order_id" not in _indexes(inspector, "orders"):
            op.create_index("ix_orders_source_order_id", "orders", ["source_order_id"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "order_items" not in tables:
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("dish_id", sa.Integer(), nullable=False),
            sa.Column("dish_name", sa.String(length=100), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_order_items_id", "order_items", ["id"])
        op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    inspector = sa.inspect(bind)
    if "reviews" not in inspector.get_table_names():
        op.create_table(
            "reviews",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("want_again", sa.String(length=20), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_id"),
        )
        op.create_index("ix_reviews_id", "reviews", ["id"])
        op.create_index("ix_reviews_order_id", "reviews", ["order_id"], unique=True)

    inspector = sa.inspect(bind)
    if "favorite_dishes" not in inspector.get_table_names():
        op.create_table(
            "favorite_dishes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.String(length=100), nullable=False),
            sa.Column("dish_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("customer_id", "dish_id", name="uq_favorite_customer_dish"),
        )
        op.create_index("ix_favorite_dishes_id", "favorite_dishes", ["id"])
        op.create_index("ix_favorite_dishes_customer_id", "favorite_dishes", ["customer_id"])
        op.create_index("ix_favorite_dishes_dish_id", "favorite_dishes", ["dish_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "favorite_dishes" in inspector.get_table_names():
        op.drop_table("favorite_dishes")

    inspector = sa.inspect(bind)
    if "orders" in inspector.get_table_names():
        indexes = _indexes(inspector, "orders")
        if "ix_orders_source_order_id" in indexes:
            op.drop_index("ix_orders_source_order_id", table_name="orders")
        columns = _columns(inspector, "orders")
        if "source_order_id" in columns:
            with op.batch_alter_table("orders") as batch_op:
                batch_op.drop_column("source_order_id")

    inspector = sa.inspect(bind)
    if "dishes" in inspector.get_table_names():
        columns = _columns(inspector, "dishes")
        with op.batch_alter_table("dishes") as batch_op:
            for name in ("tags", "spicy_level", "difficulty", "cook_time"):
                if name in columns:
                    batch_op.drop_column(name)
