import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'girlfriend_menu.db'}",
)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_order_customer_id_column():
    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("orders")}
    with engine.begin() as connection:
        if "customer_id" not in column_names:
            connection.execute(text("ALTER TABLE orders ADD COLUMN customer_id TEXT"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_orders_customer_id ON orders (customer_id)"
            )
        )


def ensure_compatible_schema():
    """Apply small, idempotent upgrades without rebuilding existing data."""
    ensure_order_customer_id_column()
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "dishes" in table_names:
            dish_columns = {column["name"] for column in inspector.get_columns("dishes")}
            if "is_active" not in dish_columns:
                default_value = "1" if engine.dialect.name == "sqlite" else "TRUE"
                connection.execute(
                    text(
                        "ALTER TABLE dishes ADD COLUMN "
                        f"is_active BOOLEAN NOT NULL DEFAULT {default_value}"
                    )
                )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_dishes_is_active ON dishes (is_active)")
            )

        if "orders" in table_names:
            order_columns = {column["name"] for column in inspector.get_columns("orders")}
            if "source_order_id" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN source_order_id INTEGER"))
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_orders_status ON orders (status)")
            )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders (created_at)")
            )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_orders_source_order_id ON orders (source_order_id)")
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
