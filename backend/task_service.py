"""Daily couple-task generation and idempotent reward settlement."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from love_score import record_score


TASK_TEMPLATES = (
    {"type": "COMPLIMENT", "title": "给对方一句真诚的夸奖", "reward": 2, "trigger": "manual"},
    {"type": "MEAL", "title": "一起完成一顿饭", "reward": 5, "trigger": "order"},
    {"type": "GAME", "title": "一起完成一局小游戏", "reward": 3, "trigger": "game"},
    {"type": "REVIEW", "title": "记录一次五星用餐感受", "reward": 3, "trigger": "review"},
)
MANUAL_TASK_TYPES = {template["type"] for template in TASK_TEMPLATES if template["trigger"] == "manual"}


def china_now() -> datetime:
    """Return a naive UTC+8 value, matching existing naive database timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)


def ensure_today_tasks(db: Session, customer_id: str) -> list[models.DailyTask]:
    today = china_now().date()
    existing = (
        db.query(models.DailyTask)
        .filter(models.DailyTask.customer_id == customer_id, models.DailyTask.date == today)
        .order_by(models.DailyTask.id)
        .all()
    )
    existing_types = {task.type for task in existing}
    additions = [
        models.DailyTask(
            customer_id=customer_id,
            title=template["title"],
            type=template["type"],
            reward_score=template["reward"],
            status="pending",
            date=today,
        )
        for template in TASK_TEMPLATES
        if template["type"] not in existing_types
    ]
    if additions:
        db.add_all(additions)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return (
        db.query(models.DailyTask)
        .filter(models.DailyTask.customer_id == customer_id, models.DailyTask.date == today)
        .order_by(models.DailyTask.id)
        .all()
    )


def _settle_task(db: Session, task: models.DailyTask) -> models.DailyTask:
    if task.status == "completed":
        return task
    task.status = "completed"
    task.completed_at = china_now()
    record_score(
        db,
        task.customer_id,
        "DAILY_TASK",
        task.reward_score,
        f"完成今日任务：{task.title}",
        task.id,
    )
    db.commit()
    db.refresh(task)
    return task


def complete_task_type(db: Session, customer_id: str | None, task_type: str):
    """Settle an automatic task after its authoritative backend event."""
    if not customer_id:
        return None
    tasks = ensure_today_tasks(db, customer_id)
    task = next((item for item in tasks if item.type == task_type), None)
    return _settle_task(db, task) if task else None


def complete_manual_task(db: Session, customer_id: str, task_id: int):
    ensure_today_tasks(db, customer_id)
    task = (
        db.query(models.DailyTask)
        .filter(models.DailyTask.id == task_id, models.DailyTask.customer_id == customer_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="今日任务不存在")
    if task.date != china_now().date():
        raise HTTPException(status_code=409, detail="只能完成今天的任务")
    if task.type not in MANUAL_TASK_TYPES:
        raise HTTPException(status_code=409, detail="该任务会在对应行为完成后自动点亮")
    return _settle_task(db, task)


def today_summary(db: Session, customer_id: str) -> dict:
    tasks = ensure_today_tasks(db, customer_id)
    completed = [task for task in tasks if task.status == "completed"]
    return {
        "date": china_now().date(),
        "completed_count": len(completed),
        "total_count": len(tasks),
        "earned_score": sum(task.reward_score for task in completed),
        "possible_score": sum(task.reward_score for task in tasks),
        "tasks": tasks,
        "recent_interactions": recent_interactions(db, customer_id, 10),
    }


def recent_interactions(db: Session, customer_id: str, limit: int = 20):
    return (
        db.query(models.GameEventLog)
        .filter(models.GameEventLog.player_id == customer_id)
        .order_by(models.GameEventLog.created_at.desc(), models.GameEventLog.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
