"""Adapters around the existing shared game-room persistence model."""
from sqlalchemy.orm import Session

import crud
import models


def create_room(db: Session, game_type: str, creator_id: str, max_players: int) -> models.GameRoom:
    """Create a catalog-validated room and set its human capacity."""
    room = crud.create_game_room(db, game_type, creator_id)
    if room.max_players != max_players:
        room.max_players = max_players
        db.commit()
        db.refresh(room)
    return room


def require_room(db: Session, room_code: str, game_type: str) -> models.GameRoom:
    """Load a room and reject accidental cross-game state access."""
    room = crud.get_game_room(db, room_code)
    if room.game_type != game_type:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="房间类型与当前游戏不匹配")
    return room
