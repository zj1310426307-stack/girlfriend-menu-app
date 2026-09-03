"""Dish catalogue, favorites and dish administration routes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

import schemas
from api.dependencies import get_customer_id, verify_admin_token
from database import get_db
from services import dish_service, favorite_service


router = APIRouter()


@router.get("/api/dishes", response_model=list[schemas.DishOut])
def dishes(category: str | None = None, db: Session = Depends(get_db)):
    """List active dishes, optionally restricted to one category."""
    return dish_service.list_dishes(db, category)


@router.get("/api/dishes/{dish_id}", response_model=schemas.DishOut)
def dish_detail(dish_id: int, db: Session = Depends(get_db)):
    """Return one active dish or the existing not-found response."""
    return dish_service.get_dish(db, dish_id)


@router.get("/api/favorites", response_model=list[schemas.DishOut])
def favorite_dishes(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """List dishes favorited by the authenticated customer."""
    return favorite_service.list_favorite_dishes(db, customer_id)


@router.post("/api/favorites/{dish_id}", response_model=schemas.DishOut)
def add_favorite(
    dish_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Add one dish to the authenticated customer's favorites."""
    return favorite_service.add_favorite_dish(db, customer_id, dish_id)


@router.delete("/api/favorites/{dish_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    dish_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Remove one owned favorite without altering the dish."""
    favorite_service.remove_favorite_dish(db, customer_id, dish_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/api/dishes",
    response_model=schemas.DishOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_token)],
)
def add_dish(data: schemas.DishCreate, db: Session = Depends(get_db)):
    """Create a dish through the administrator-only catalogue endpoint."""
    return dish_service.create_dish(db, data)


@router.put(
    "/api/dishes/{dish_id}",
    response_model=schemas.DishOut,
    dependencies=[Depends(verify_admin_token)],
)
def edit_dish(dish_id: int, data: schemas.DishUpdate, db: Session = Depends(get_db)):
    """Update one dish while preserving the existing schema and status codes."""
    return dish_service.update_dish(db, dish_id, data)


@router.delete(
    "/api/dishes/{dish_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_admin_token)],
)
def remove_dish(dish_id: int, db: Session = Depends(get_db)):
    """Soft-delete a dish through the administrator-only endpoint."""
    dish_service.delete_dish(db, dish_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/api/stats/favorite-ranking",
    response_model=list[schemas.FavoriteRankingItem],
)
def favorite_ranking(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the current customer's dish ranking without changing its formula."""
    return favorite_service.rank_favorite_dishes(db, customer_id)
