"""Achievement progress, idempotent unlocks and reward settlement."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from love_score import record_score


def _progress(db: Session, customer_id: str, achievement: models.Achievement) -> int:
    """Calculate one achievement metric from durable completed records."""
    query = (
        db.query(func.count(models.GameRecord.id))
        .join(models.GameRoom, models.GameRecord.room_id == models.GameRoom.id)
        .join(models.GamePlayer, models.GamePlayer.room_id == models.GameRoom.id)
        .filter(models.GamePlayer.player_id == customer_id)
    )
    if achievement.game_type:
        query = query.filter(models.GameRecord.game_type == achievement.game_type)
    if achievement.metric == "wins":
        query = query.filter(models.GameRecord.winner == customer_id)
    return int(query.scalar() or 0)


def evaluate_achievements(db: Session, customer_id: str) -> list[models.UserAchievement]:
    """Unlock every newly satisfied definition exactly once."""
    definitions = (
        db.query(models.Achievement)
        .filter(models.Achievement.enabled.is_(True))
        .order_by(models.Achievement.id)
        .all()
    )
    unlocked_ids = {
        achievement_id
        for (achievement_id,) in db.query(models.UserAchievement.achievement_id)
        .filter(models.UserAchievement.customer_id == customer_id)
        .all()
    }
    created = []
    for definition in definitions:
        if definition.id in unlocked_ids or _progress(db, customer_id, definition) < definition.threshold:
            continue
        entry = models.UserAchievement(
            customer_id=customer_id,
            achievement_id=definition.id,
        )
        db.add(entry)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(entry)
        created.append(entry)
        if definition.reward_score:
            record_score(
                db,
                customer_id,
                "ACHIEVEMENT",
                definition.reward_score,
                f"解锁成就：{definition.name}",
                definition.id,
            )
    return created


def achievement_catalog(db: Session, customer_id: str) -> list[dict]:
    """Return definitions together with viewer-specific progress and unlock state."""
    definitions = (
        db.query(models.Achievement)
        .filter(models.Achievement.enabled.is_(True))
        .order_by(models.Achievement.id)
        .all()
    )
    unlocked = {
        item.achievement_id: item.created_at
        for item in db.query(models.UserAchievement)
        .filter(models.UserAchievement.customer_id == customer_id)
        .all()
    }
    return [
        {
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "description": item.description,
            "reward_score": item.reward_score,
            "game_type": item.game_type,
            "metric": item.metric,
            "threshold": item.threshold,
            "progress": min(item.threshold, _progress(db, customer_id, item)),
            "unlocked": item.id in unlocked,
            "unlocked_at": unlocked.get(item.id),
        }
        for item in definitions
    ]


def achievement_stats(db: Session) -> int:
    """Return total unlocked achievements for admin analytics."""
    return int(db.query(func.count(models.UserAchievement.id)).scalar() or 0)
