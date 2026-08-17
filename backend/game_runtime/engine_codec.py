"""Game-specific snapshot codecs used by the shared real-time room transport."""

from __future__ import annotations

from types import MappingProxyType
from typing import Protocol

from gomoku import GomokuGame
from games.core.lifecycle import GameStateAdapter
from games.registry import GAME_PLUGINS


class RealtimeEngineCodec(Protocol):
    """Keep engine construction and JSON recovery outside transport orchestration."""

    game_type: str

    def new_room_fields(self) -> dict:
        """Return game-owned fields for a new real-time room."""

    def snapshot_engine(self, room: dict) -> dict | None:
        """Serialize only the game engine portion of a room."""

    def restore_engine(self, room: dict, raw: dict | None) -> None:
        """Restore the game engine portion into an existing room container."""


class DiceEngineCodec:
    """Represent dice state that already lives in the common room snapshot."""

    game_type = "dice"

    def new_room_fields(self) -> dict:
        return {}

    def snapshot_engine(self, room: dict) -> None:
        del room
        return None

    def restore_engine(self, room: dict, raw: dict | None) -> None:
        del room, raw


class CompatibilityEngineCodec(DiceEngineCodec):
    """Preserve generic room creation for games owned by an HTTP state service."""

    def __init__(self, game_type: str):
        self.game_type = game_type


class GomokuEngineCodec:
    """Construct and restore the pure Gomoku engine used by WebSocket rooms."""

    game_type = "gomoku"

    def new_room_fields(self) -> dict:
        return {"gomoku": GomokuGame()}

    def snapshot_engine(self, room: dict) -> dict:
        return room["gomoku"].serialize()

    def restore_engine(self, room: dict, raw: dict | None) -> None:
        if not raw:
            return
        engine = GomokuGame()
        for player in raw.get("players") or []:
            engine.add_player(player["id"])
        engine.board = [list(row) for row in raw.get("board") or engine.board]
        engine.phase = raw.get("phase", engine.phase)
        engine.turn_id = raw.get("turn_id")
        engine.winner_id = raw.get("winner_id")
        engine.last_move = raw.get("last_move")
        engine.move_count = int(raw.get("move_count") or 0)
        engine.move_history = list(raw.get("move_history") or [])
        engine.round = int(raw.get("round") or 1)
        engine.is_draw = bool(raw.get("is_draw"))
        room["gomoku"] = engine


REALTIME_ENGINE_CODECS: dict[str, RealtimeEngineCodec] = MappingProxyType({
    "dice": DiceEngineCodec(),
    "gomoku": GomokuEngineCodec(),
})


def get_realtime_engine_codec(game_type: str) -> RealtimeEngineCodec:
    """Resolve aliases through the game registry and reject non-realtime games."""
    plugin = GAME_PLUGINS.resolve(game_type)
    if plugin.state_adapter != GameStateAdapter.REALTIME_ROOM:
        raise LookupError(f"游戏 {plugin.game_type} 不使用实时房间状态")
    try:
        return REALTIME_ENGINE_CODECS[plugin.game_type]
    except KeyError as error:
        raise LookupError(f"游戏 {plugin.game_type} 缺少实时引擎 codec") from error


def get_room_engine_codec(game_type: str) -> RealtimeEngineCodec:
    """Return a strict real-time codec or a metadata-only compatibility codec."""
    plugin = GAME_PLUGINS.resolve(game_type)
    if plugin.state_adapter == GameStateAdapter.REALTIME_ROOM:
        return get_realtime_engine_codec(plugin.game_type)
    return CompatibilityEngineCodec(plugin.game_type)


__all__ = [
    "REALTIME_ENGINE_CODECS",
    "RealtimeEngineCodec",
    "get_realtime_engine_codec",
    "get_room_engine_codec",
]
