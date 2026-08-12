"""Integration contracts for the Phase 2B Dish/Favorite service boundaries."""

import uuid

import pytest
from fastapi import HTTPException

from test_api import app  # noqa: F401  Ensures the shared test environment is initialized.

import crud
import schemas
from database import Base, SessionLocal, engine
from services import dish_service, favorite_service


@pytest.fixture(scope="module", autouse=True)
def service_schema():
    """Create the shared SQLite schema when this contract file runs alone."""
    Base.metadata.create_all(bind=engine)


def _dish_payload(name: str, price: float = 22.0) -> schemas.DishCreate:
    """Build a unique service-level dish payload for the shared SQLite database."""
    return schemas.DishCreate(
        name=name,
        description="Phase 2B service contract",
        category="service-test",
        price=price,
        image_url="",
    )


def test_dish_service_preserves_snapshot_when_catalogue_changes():
    """Updating and disabling a dish never rewrites its historical order snapshot."""
    marker = uuid.uuid4().hex[:10]
    customer_id = f"gf_service_snapshot_{marker}"
    original_name = f"snapshot-original-{marker}"
    with SessionLocal() as db:
        dish = dish_service.create_dish(db, _dish_payload(original_name, 23.0))
        order = crud.create_order(
            db,
            schemas.OrderCreate(
                items=[schemas.OrderItemCreate(dish_id=dish.id, quantity=2)],
                customer_id=customer_id,
            ),
        )
        original_price = order.items[0].price

        dish_service.update_dish(
            db,
            dish.id,
            schemas.DishUpdate(
                name=f"snapshot-updated-{marker}",
                description="updated",
                category="service-test",
                price=99.0,
                image_url="",
            ),
        )
        dish_service.delete_dish(db, dish.id)

        db.expire_all()
        historical = crud.get_order(db, order.id)
        assert historical.items[0].dish_name == original_name
        assert historical.items[0].price == original_price
        with pytest.raises(HTTPException) as missing:
            dish_service.get_dish(db, dish.id)
        assert missing.value.status_code == 404


def test_favorite_service_preserves_idempotency_isolation_and_absent_remove():
    """Service orchestration scopes rows per customer and keeps removals idempotent."""
    marker = uuid.uuid4().hex[:10]
    first_customer = f"gf_service_first_{marker}"
    second_customer = f"gf_service_second_{marker}"
    with SessionLocal() as db:
        dish = dish_service.create_dish(db, _dish_payload(f"service-favorite-{marker}"))
        favorite_service.add_favorite_dish(db, first_customer, dish.id)
        favorite_service.add_favorite_dish(db, first_customer, dish.id)

        assert [
            item.id for item in favorite_service.list_favorite_dishes(db, first_customer)
        ] == [dish.id]
        assert favorite_service.list_favorite_dishes(db, second_customer) == []

        favorite_service.remove_favorite_dish(db, second_customer, dish.id)
        assert len(favorite_service.list_favorite_dishes(db, first_customer)) == 1
        favorite_service.remove_favorite_dish(db, first_customer, dish.id)
        favorite_service.remove_favorite_dish(db, first_customer, dish.id)
        assert favorite_service.list_favorite_dishes(db, first_customer) == []
