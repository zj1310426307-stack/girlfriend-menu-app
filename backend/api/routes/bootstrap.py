"""Authenticated home bootstrap endpoint for latency-sensitive mini programs."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import schemas
from api.dependencies import get_customer_id
from database import get_db
from services import bootstrap_service


router = APIRouter()


@router.get("/api/bootstrap", response_model=schemas.HomeBootstrapOut)
def home_bootstrap(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Aggregate the five existing home reads without replacing their endpoints."""
    return bootstrap_service.build_home_bootstrap(db, customer_id)
