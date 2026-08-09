"""Shared human-player membership helpers."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

import crud
import models


def join(db: Session, room_code: str, player_id: str) -> models.GamePlayer:
    """Join one human seat using the existing idempotent room logic."""
    return crud.join_game_room(db, room_code, player_id)


def players(db: Session, room_id: int) -> list[models.GamePlayer]:
    """List persisted human seats in deterministic order."""
    return (
        db.query(models.GamePlayer)
        .filter(models.GamePlayer.room_id == room_id)
        .order_by(models.GamePlayer.seat)
        .all()
    )


def require_member(db: Session, room_id: int, player_id: str) -> models.GamePlayer:
    """Ensure a device identity belongs to the room before revealing state."""
    player = (
        db.query(models.GamePlayer)
        .filter(
            models.GamePlayer.room_id == room_id,
            models.GamePlayer.player_id == player_id,
        )
        .first()
    )
    if not player:
        raise HTTPException(status_code=403, detail="你还没有加入这个房间")
    return player
