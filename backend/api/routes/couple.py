"""Couple profile, memories, dates, scores and daily-task routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

import couple_profile_service
import love_score
import notification_service
import schemas
import task_service
from api.dependencies import get_customer_id, verify_admin_token
from database import get_db


router = APIRouter()


@router.get("/api/couple/memories", response_model=list[schemas.CoupleMemoryOut])
def couple_memories(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """List the authenticated couple's durable timeline memories."""
    return couple_profile_service.list_memories(db, customer_id)


@router.post(
    "/api/couple/memories",
    response_model=schemas.CoupleMemoryOut,
    status_code=status.HTTP_201_CREATED,
)
def add_couple_memory(
    data: schemas.CoupleMemoryCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Append one memory to the authenticated couple timeline."""
    return couple_profile_service.add_memory(db, customer_id, data)


@router.delete("/api/couple/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_couple_memory(
    memory_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Delete one owned couple memory."""
    couple_profile_service.delete_memory(db, customer_id, memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/couple/dates", response_model=list[schemas.CoupleDateOut])
def couple_dates(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """List anniversaries belonging to the authenticated couple."""
    return couple_profile_service.list_dates(db, customer_id)


@router.post(
    "/api/couple/dates",
    response_model=schemas.CoupleDateOut,
    status_code=status.HTTP_201_CREATED,
)
def add_couple_date(
    data: schemas.CoupleDateCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create an anniversary and its one-time timeline memory."""
    item = couple_profile_service.add_date(db, customer_id, data)
    couple_profile_service.record_memory_once(
        db,
        customer_id,
        "ANNIVERSARY",
        f"记住了：{item.title}",
        "以后每个重要日子都不会悄悄错过。",
        "COUPLE_DATE",
        item.id,
        item.date,
    )
    return item


@router.delete("/api/couple/dates/{date_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_couple_date(
    date_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Delete one owned anniversary without altering other memories."""
    couple_profile_service.delete_date(db, customer_id, date_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/couple/profile", response_model=schemas.CoupleProfileSummaryOut)
def couple_profile(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the couple home summary after generating due reminders."""
    notification_service.generate_anniversary_reminders(db, customer_id)
    return couple_profile_service.profile_summary(db, customer_id)


@router.get("/api/couple/statistics", response_model=schemas.CoupleStatisticsOut)
def couple_statistics(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return aggregate food, game and interaction statistics."""
    return couple_profile_service.statistics(db, customer_id)


@router.get("/api/couple/score", response_model=schemas.LoveScoreSummary)
def couple_score(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the current love-score summary and level."""
    return love_score.score_summary(db, customer_id)


@router.get("/api/couple/score/history", response_model=list[schemas.LoveScoreOut])
def couple_score_history(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the authenticated customer's love-score ledger."""
    return love_score.score_history(db, customer_id)


@router.get("/api/couple/tasks/today", response_model=schemas.DailyTaskSummary)
def couple_tasks_today(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return today's generated couple tasks and completion progress."""
    return task_service.today_summary(db, customer_id)


@router.post("/api/couple/tasks/{task_id}/complete", response_model=schemas.DailyTaskOut)
def complete_couple_task(
    task_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Complete one manual task and preserve the service's idempotent reward behavior."""
    return task_service.complete_manual_task(db, customer_id, task_id)


@router.post(
    "/api/couple/score/add",
    response_model=schemas.LoveScoreOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_token)],
)
def add_couple_score(
    data: schemas.LoveScoreCreate,
    x_customer_id: str | None = Header(default=None, alias="X-Customer-Id"),
    db: Session = Depends(get_db),
):
    """Allow an administrator to append an attributed score ledger entry."""
    customer_id = (x_customer_id or "").strip()[:100]
    if not customer_id:
        raise HTTPException(status_code=422, detail="请选择积分所属用户")
    return love_score.record_score(
        db,
        customer_id,
        data.type,
        data.score,
        data.description,
        data.related_id,
    )
