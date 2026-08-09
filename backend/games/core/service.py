"""Shared completion pipeline for V2.5 persisted game sessions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import models
from achievement_service import evaluate_achievements
from game_rewards import settle_game_rewards
from love_score import record_score
from game_recovery_service import save_replay
from couple_profile_service import record_memory_once
from notification_service import create_notification


LANDLORD_TASKS = (
    "输的人负责准备下一次饭后水果",
    "赢家决定下一次约会的小环节",
    "给对方说一句今天最真诚的夸奖",
)


def _love_tasks(db: Session, record: models.GameRecord, player_ids: list[str]) -> None:
    """Create one lightweight couple action per human after landlord finishes."""
    if record.game_type != "landlord":
        return
    for index, player_id in enumerate(player_ids):
        existing = (
            db.query(models.LoveTask)
            .filter(
                models.LoveTask.game_record_id == record.id,
                models.LoveTask.player_id == player_id,
            )
            .first()
        )
        if existing:
            continue
        db.add(
            models.LoveTask(
                game_record_id=record.id,
                player_id=player_id,
                title=LANDLORD_TASKS[(record.id + index) % len(LANDLORD_TASKS)],
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def settle_session_game(
    db: Session,
    room: models.GameRoom,
    state: dict,
    winner_id: str | None,
    difficulty: str = "rule",
) -> models.GameRecord:
    """Persist record, scores, tasks and achievements once for a finished session."""
    existing = (
        db.query(models.GameRecord)
        .filter(models.GameRecord.room_id == room.id, models.GameRecord.round_number == state.get("round", 1))
        .first()
    )
    if existing and (existing.result or {}).get("_settlement") == "complete":
        return existing
    started_at = state.get("started_at")
    try:
        duration = max(0, int((datetime.now() - datetime.fromisoformat(started_at)).total_seconds()))
    except (TypeError, ValueError):
        duration = 0
    result = {
        "phase": state.get("phase"),
        "winner_id": winner_id,
        "difficulty": difficulty,
        "mode": state.get("mode"),
        "_settlement": "pending",
    }
    record = crud.finish_game_room(
        db,
        room.room_code,
        winner_id,
        duration,
        result,
        state.get("round", 1),
    )
    human_ids = [player.player_id for player in record.players]
    settle_game_rewards(db, record, human_ids, winner_id)
    if winner_id in human_ids:
        participant_ids = [
            item.get("id") if isinstance(item, dict) else item
            for item in state.get("players", [])
        ]
        against_ai = any(str(item).startswith("ai_") for item in participant_ids)
        bonus = 2 if against_ai and difficulty in {"random", "rule"} else 8 if against_ai else 10
        record_score(
            db,
            winner_id,
            "GAME_BONUS",
            bonus,
            "战胜 AI 奖励" if against_ai else "双人对战胜利奖励",
            record.id,
        )
    _love_tasks(db, record, human_ids)
    for player_id in human_ids:
        evaluate_achievements(db, player_id)
        record_memory_once(
            db,
            player_id,
            "GAME",
            "一起完成了一局游戏",
            f"{record.game_type} · {record.duration} 秒",
            "GAME_RECORD",
            record.id,
            record.created_at.date(),
        )
        create_notification(
            db,
            player_id,
            "GAME_FINISHED",
            "一局游戏已经结束",
            f"{record.game_type} 的结果和回放已经保存。",
            record.id,
        )
    save_replay(db, record, state)
    record.result = {**(record.result or {}), "_settlement": "complete"}
    db.commit()
    db.refresh(record)
    return record


def list_love_tasks(db: Session, customer_id: str, limit: int = 50) -> list[models.LoveTask]:
    """Return recent post-game interaction tasks for one device identity."""
    return (
        db.query(models.LoveTask)
        .filter(models.LoveTask.player_id == customer_id)
        .order_by(models.LoveTask.created_at.desc(), models.LoveTask.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )


def complete_love_task(db: Session, customer_id: str, task_id: int) -> models.LoveTask:
    """Complete one owned post-game promise and award a small idempotent bonus."""
    from fastapi import HTTPException

    task = (
        db.query(models.LoveTask)
        .filter(models.LoveTask.id == task_id, models.LoveTask.player_id == customer_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="牌局互动任务不存在")
    if task.status != "completed":
        task.status = "completed"
        task.completed_at = datetime.now()
        db.commit()
        record_score(db, customer_id, "LOVE_TASK", 2, f"完成牌局约定：{task.title}", task.id)
        db.refresh(task)
    return task
