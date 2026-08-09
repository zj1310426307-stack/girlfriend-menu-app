from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models


LEVELS = (
    (0, "初识", 50),
    (50, "熟悉", 100),
    (100, "默契搭档", 200),
    (200, "灵魂搭档", None),
)


def record_score(
    db: Session,
    customer_id: str | None,
    score_type: str,
    score: int,
    description: str,
    related_id: int | None = None,
):
    """Persist one score source and make automatic triggers idempotent."""
    if not customer_id:
        return None
    if related_id is not None:
        existing = (
            db.query(models.LoveScore)
            .filter(
                models.LoveScore.customer_id == customer_id,
                models.LoveScore.type == score_type,
                models.LoveScore.related_id == related_id,
            )
            .first()
        )
        if existing:
            return existing
    entry = models.LoveScore(
        customer_id=customer_id,
        score=score,
        type=score_type,
        description=description,
        related_id=related_id,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if related_id is not None:
            return (
                db.query(models.LoveScore)
                .filter(
                    models.LoveScore.customer_id == customer_id,
                    models.LoveScore.type == score_type,
                    models.LoveScore.related_id == related_id,
                )
                .first()
            )
        raise
    db.refresh(entry)
    return entry


def score_history(db: Session, customer_id: str, limit: int = 100):
    return (
        db.query(models.LoveScore)
        .filter(models.LoveScore.customer_id == customer_id)
        .order_by(models.LoveScore.created_at.desc(), models.LoveScore.id.desc())
        .limit(limit)
        .all()
    )


def _level_for(total: int):
    current = LEVELS[0]
    for level in LEVELS:
        if total >= level[0]:
            current = level
    minimum, name, next_level_at = current
    if next_level_at is None:
        progress = 100
    else:
        progress = round((total - minimum) / (next_level_at - minimum) * 100)
    return name, next_level_at, max(0, min(100, progress))


def score_summary(db: Session, customer_id: str):
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    recent_start = now - timedelta(days=30)
    entries = (
        db.query(models.LoveScore)
        .filter(models.LoveScore.customer_id == customer_id)
        .all()
    )
    points_total = sum(entry.score for entry in entries)
    month_entries = [entry for entry in entries if entry.created_at >= month_start]
    recent_entries = [entry for entry in entries if entry.created_at >= recent_start]
    shared_sources = {
        (entry.type, entry.related_id)
        for entry in entries
        if entry.related_id is not None
    }
    review_stats = (
        db.query(func.avg(models.Review.rating), func.count(models.Review.id))
        .join(models.Order, models.Order.id == models.Review.order_id)
        .filter(models.Order.customer_id == customer_id)
        .first()
    )
    average_rating = float(review_stats[0] or 0)
    review_count = int(review_stats[1] or 0)

    recent_component = min(200, len(recent_entries) * 12) * 0.4
    experience_component = min(300, len(shared_sources) * 10) * 0.3
    feedback_confidence = min(1, review_count / 10)
    satisfaction_component = (average_rating / 5 * 200) * feedback_confidence * 0.3
    total = round(recent_component + experience_component + satisfaction_component)
    level, next_level_at, progress = _level_for(total)

    completed_orders = (
        db.query(func.count(models.Order.id))
        .filter(
            models.Order.customer_id == customer_id,
            models.Order.status == "已完成",
            models.Order.created_at >= month_start,
        )
        .scalar()
        or 0
    )
    month_games = sum(entry.type == "GAME_PLAY" for entry in month_entries)
    month_encouragement = sum(
        entry.type in {
            "ORDER_REVIEW",
            "SPECIAL_EVENT",
            "GAME_EVENT",
            "DAILY_TASK",
            "GAME_BONUS",
            "ACHIEVEMENT",
            "LOVE_TASK",
        }
        for entry in month_entries
    )
    return {
        "total": total,
        "level": level,
        "month_score": sum(entry.score for entry in month_entries),
        "points_total": points_total,
        "next_level_at": next_level_at,
        "progress": progress,
        "month_meals": int(completed_orders),
        "month_games": month_games,
        "month_encouragement": month_encouragement,
        "breakdown": {
            "recent_interaction": round(recent_component),
            "shared_experience": round(experience_component),
            "satisfaction_feedback": round(satisfaction_component),
        },
    }
