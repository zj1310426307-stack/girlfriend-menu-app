"""Framework-free lifecycle capabilities shared by every LoveOS game plugin."""

from __future__ import annotations

from enum import StrEnum


class LifecycleOperation(StrEnum):
    """Stable platform operations exposed by a game implementation."""

    CREATE = "create"
    JOIN = "join"
    START = "start"
    ACTION = "action"
    VALIDATE = "validate"
    FINISH = "finish"
    RECOVER = "recover"
    REPLAY = "replay"


STANDARD_LIFECYCLE = tuple(LifecycleOperation)


class GameStateAdapter(StrEnum):
    """Name the existing authoritative state path without importing it here."""

    REALTIME_ROOM = "realtime_room"
    FLIGHT_STATE = "flight_state"
    VERSIONED_SESSION = "versioned_session"


class GameTransport(StrEnum):
    """Transport families supported by the current compatibility surface."""

    HTTP = "http"
    WEBSOCKET = "websocket"


__all__ = [
    "GameStateAdapter",
    "GameTransport",
    "LifecycleOperation",
    "STANDARD_LIFECYCLE",
]
