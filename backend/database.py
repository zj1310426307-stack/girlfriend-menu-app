from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from core.settings import get_settings


BASE_DIR = Path(__file__).resolve().parent


def configured_database_url() -> str:
    """Return the current normalized URL without exposing it through Settings repr."""
    return get_settings().normalized_database_url


def database_engine_options(database_url: str) -> dict:
    """Build the same SQLite or bounded PostgreSQL engine options as before."""
    options = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    else:
        settings = get_settings()
        options.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )
    return options


DATABASE_URL = configured_database_url()
engine_options = database_engine_options(DATABASE_URL)

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
            for column_name, column_type in (
                ("cook_time", "INTEGER"),
                ("difficulty", "INTEGER"),
                ("spicy_level", "INTEGER"),
                ("tags", "JSON"),
            ):
                if column_name not in dish_columns:
                    connection.execute(
                        text(f"ALTER TABLE dishes ADD COLUMN {column_name} {column_type}")
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

        if "game_rooms" in table_names:
            room_columns = {
                column["name"] for column in inspector.get_columns("game_rooms")
            }
            if "finished_at" not in room_columns:
                connection.execute(
                    # TIMESTAMP is understood by both PostgreSQL and SQLite.
                    text("ALTER TABLE game_rooms ADD COLUMN finished_at TIMESTAMP")
                )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_game_rooms_finished_at ON game_rooms (finished_at)"
                )
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
