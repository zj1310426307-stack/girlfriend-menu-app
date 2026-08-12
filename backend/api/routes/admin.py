"""Administrator dashboard and aggregate statistics routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import crud
import schemas
import system_stats_service
from api.dependencies import verify_admin_token
from database import get_db


router = APIRouter()


@router.get(
    "/api/admin/dashboard",
    dependencies=[Depends(verify_admin_token)],
)
def admin_dashboard(db: Session = Depends(get_db)):
    """Return the existing administrator data cockpit payload."""
    return system_stats_service.admin_dashboard(db)


@router.get(
    "/api/admin/games/stats",
    response_model=schemas.GameStatsOut,
    dependencies=[Depends(verify_admin_token)],
)
def admin_game_stats(db: Session = Depends(get_db)):
    """Return aggregate game statistics for the administrator."""
    return crud.game_stats(db)


@router.get(
    "/api/stats/summary",
    response_model=schemas.StatsSummary,
    dependencies=[Depends(verify_admin_token)],
)
def stats_summary(db: Session = Depends(get_db)):
    """Return aggregate order counts for the administrator."""
    return crud.get_stats_summary(db)


@router.get(
    "/api/stats/dishes",
    response_model=list[schemas.DishStats],
    dependencies=[Depends(verify_admin_token)],
)
def stats_dishes(db: Session = Depends(get_db)):
    """Return per-dish order statistics for the administrator."""
    return crud.get_dish_stats(db)


@router.get(
    "/api/stats/recent",
    response_model=list[schemas.OrderOut],
    dependencies=[Depends(verify_admin_token)],
)
def stats_recent(db: Session = Depends(get_db)):
    """Return the existing recent-order statistics slice."""
    return crud.get_recent_orders(db)
