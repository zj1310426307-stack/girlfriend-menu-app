"""Adapters from stable game APIs to the V3 plugin-backed internal services."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

import animal_service
import flight_service
import models
from game_runtime import game_room_manager
from games.registry import GAME_PLUGINS
from services import game_persistence_service


async def recover_game_state(
    db: Session,
    room: models.GameRoom,
    player_id: str,
) -> dict:
    """Recover every deployed game type through its existing authoritative backend."""
    try:
        plugin = GAME_PLUGINS.resolve(room.game_type)
    except LookupError:
        return {
            "room_code": room.room_code,
            "game_type": room.game_type,
            "room_status": room.status,
            "reconnect_required": True,
        }

    if plugin.game_type == "aeroplane":
        return flight_service.get_state(db, room.room_code, player_id)
    if plugin.engine_factory is not None:
        return animal_service.get_any_state(db, room.room_code, player_id)
    if plugin.game_type in {"dice", "gomoku"}:
        await game_room_manager.ensure_room(
            room.room_code,
            plugin.game_type,
            room.max_players,
        )
        await game_room_manager.restore_players(
            room.room_code,
            game_persistence_service.list_game_players(db, room.room_code),
        )
        payload = await game_room_manager.recovery_state(room.room_code, player_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="游戏状态暂时无法恢复")
        return payload
    return {
        "room_code": room.room_code,
        "game_type": plugin.game_type,
        "room_status": room.status,
        "reconnect_required": True,
    }
