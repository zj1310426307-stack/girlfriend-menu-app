"""Adapters from stable game APIs to the V3 plugin-backed internal services."""

from collections.abc import Awaitable, Callable
from types import MappingProxyType

from fastapi import HTTPException
from sqlalchemy.orm import Session

import animal_service
import flight_service
import models
from game_runtime import game_room_manager
from games.core.lifecycle import GameStateAdapter
from games.registry import GAME_PLUGINS
from services import game_persistence_service


async def _recover_flight_state(
    db: Session,
    room: models.GameRoom,
    player_id: str,
) -> dict:
    """Delegate flight recovery to its existing versioned state service."""
    return flight_service.get_state(db, room.room_code, player_id)


async def _recover_versioned_session(
    db: Session,
    room: models.GameRoom,
    player_id: str,
) -> dict:
    """Delegate pure-engine sessions to the existing compatibility service."""
    return animal_service.get_any_state(db, room.room_code, player_id)


async def _recover_realtime_room(
    db: Session,
    room: models.GameRoom,
    player_id: str,
) -> dict:
    """Restore a leased real-time room and return a viewer-filtered snapshot."""
    plugin = GAME_PLUGINS.resolve(room.game_type)
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


RecoveryHandler = Callable[[Session, models.GameRoom, str], Awaitable[dict]]
RECOVERY_HANDLERS: dict[GameStateAdapter, RecoveryHandler] = MappingProxyType({
    GameStateAdapter.FLIGHT_STATE: _recover_flight_state,
    GameStateAdapter.VERSIONED_SESSION: _recover_versioned_session,
    GameStateAdapter.REALTIME_ROOM: _recover_realtime_room,
})


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

    return await RECOVERY_HANDLERS[plugin.state_adapter](db, room, player_id)
