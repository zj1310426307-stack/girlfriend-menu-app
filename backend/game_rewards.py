"""Shared game-record and Love Score settlement for every multiplayer game."""
from sqlalchemy.orm import Session

import models
from love_score import record_score
from task_service import complete_task_type


GAME_NAMES = {
    "gomoku": "五子棋",
    "aeroplane": "情侣飞行棋",
    "dice": "大话骰",
    "landlord": "斗地主",
    "jungle": "斗兽棋",
    "chinese_chess": "中国象棋",
}


def win_streak(db: Session, game_type: str, winner_id: str) -> int:
    records = (
        db.query(models.GameRecord.winner)
        .filter(models.GameRecord.game_type == game_type)
        .order_by(models.GameRecord.created_at.desc(), models.GameRecord.id.desc())
        .limit(100)
        .all()
    )
    streak = 0
    for (winner,) in records:
        if winner != winner_id:
            break
        streak += 1
    return streak


def settle_game_rewards(
    db: Session,
    record: models.GameRecord,
    player_ids: list[str],
    winner_id: str | None,
):
    game_name = GAME_NAMES.get(record.game_type, "小游戏")
    human_ids = [player_id for player_id in player_ids if not player_id.startswith("ai_")]
    for player_id in human_ids:
        record_score(db, player_id, "GAME_PLAY", 1, f"一起完成一局{game_name}", record.id)
        complete_task_type(db, player_id, "GAME")
    if not winner_id or winner_id.startswith("ai_"):
        return record
    record_score(db, winner_id, "GAME_WIN", 5, f"{game_name}胜利", record.id)
    streak = win_streak(db, record.game_type, winner_id)
    if streak and streak % 3 == 0:
        record_score(db, winner_id, "SPECIAL_EVENT", 10, f"{game_name}三连胜", record.id)
    return record
