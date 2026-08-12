"""Real SQLite contracts for the Phase 2B Dish/Favorite repositories."""

import uuid

import pytest

from test_api import app  # noqa: F401  Ensures the shared test environment is initialized.

import schemas
from database import Base, SessionLocal, engine
from repositories import dishes as dishes_repository
from repositories import favorites as favorites_repository


@pytest.fixture(scope="module", autouse=True)
def repository_schema():
    """Create the shared SQLite schema when this contract file runs alone."""
    Base.metadata.create_all(bind=engine)


def _dish_payload(name: str) -> schemas.DishCreate:
    """Build one unique catalogue item without relying on seeded dish IDs."""
    return schemas.DishCreate(
        name=name,
        description="Phase 2B repository contract",
        category="repository-test",
        price=18.5,
        image_url="",
    )


def test_dish_repository_preserves_active_filter_update_and_soft_delete():
    """Repository queries exclude inactive rows and retain commit/refresh behavior."""
    marker = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        dish = dishes_repository.create(db, _dish_payload(f"repo-dish-{marker}"))
        assert dishes_repository.find_active(db, dish.id).id == dish.id
        assert dish.id in {
            item.id for item in dishes_repository.list_active(db, "repository-test")
        }

        updated = dishes_repository.update(
            db,
            dish,
            schemas.DishUpdate(
                name=f"repo-dish-updated-{marker}",
                description="updated",
                category="repository-test",
                price=19.5,
                image_url="",
            ),
        )
        assert updated.name == f"repo-dish-updated-{marker}"

        dishes_repository.disable(db, updated)
        assert dishes_repository.find_active(db, updated.id) is None
        assert updated.id not in {
            item.id for item in dishes_repository.list_active(db, "repository-test")
        }


def test_favorite_repository_isolates_customers_and_keeps_unique_insert_idempotent():
    """Owned favorite rows remain isolated and duplicate inserts do not multiply rows."""
    marker = uuid.uuid4().hex[:10]
    first_customer = f"gf_repo_first_{marker}"
    second_customer = f"gf_repo_second_{marker}"
    with SessionLocal() as db:
        dish = dishes_repository.create(db, _dish_payload(f"favorite-dish-{marker}"))
        favorites_repository.add(db, first_customer, dish.id)
        favorites_repository.add(db, first_customer, dish.id)

        assert len(favorites_repository.list_active_dishes(db, first_customer)) == 1
        assert favorites_repository.list_active_dishes(db, second_customer) == []
        owned = favorites_repository.find(db, first_customer, dish.id)
        assert owned is not None

        favorites_repository.remove(db, owned)
        assert favorites_repository.find(db, first_customer, dish.id) is None
        assert favorites_repository.list_active_dishes(db, first_customer) == []
