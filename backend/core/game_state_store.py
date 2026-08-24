"""Durable state boundary for real-time games with optional hot caches."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
import logging
import time

from sqlalchemy.exc import IntegrityError

from core.cache import state_cache
from core.logging_privacy import opaque_log_reference
from core.telemetry import set_span_attribute, trace_span


logger = logging.getLogger(__name__)


class GameStateStore(ABC):
    @abstractmethod
    def get(self, room_code: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, room_code: str, state: dict, ttl_seconds: int = 900) -> None:
        raise NotImplementedError


class MemoryGameStateStore(GameStateStore):
    def __init__(self):
        self._states: dict[str, tuple[float, dict]] = {}

    def get(self, room_code: str) -> dict | None:
        key = room_code.upper()
        item = self._states.get(key)
        if not item:
            return None
        expires_at, state = item
        if expires_at <= time.time():
            self._states.pop(key, None)
            return None
        return deepcopy(state)

    def set(self, room_code: str, state: dict, ttl_seconds: int = 900) -> None:
        self._states[room_code.upper()] = (time.time() + ttl_seconds, deepcopy(state))


class RedisGameStateStore(GameStateStore):
    def get(self, room_code: str) -> dict | None:
        return state_cache.get_game_state(room_code)

    def set(self, room_code: str, state: dict, ttl_seconds: int = 900) -> None:
        state_cache.set_game_state(room_code, state, ttl=ttl_seconds)


class DatabaseGameStateStore(GameStateStore):
    """Persist room snapshots in the existing ``game_states`` table.

    Imports stay local so this low-level boundary can be imported during app
    startup without creating a ``models`` / ``database`` module cycle.
    """

    def get(self, room_code: str) -> dict | None:
        from database import SessionLocal
        import models

        normalized = room_code.strip().upper()
        with SessionLocal() as db:
            row = (
                db.query(models.GameState)
                .join(models.GameRoom, models.GameRoom.id == models.GameState.room_id)
                .filter(
                    models.GameRoom.room_code == normalized,
                    models.GameRoom.game_type.in_(("dice", "gomoku")),
                )
                .first()
            )
            return deepcopy(row.state) if row else None

    def set(self, room_code: str, state: dict, ttl_seconds: int = 900) -> None:
        del ttl_seconds  # PostgreSQL is durable; room lifecycle owns expiry.

        from database import SessionLocal
        import models

        normalized = room_code.strip().upper()
        with SessionLocal() as db:
            room = (
                db.query(models.GameRoom)
                .filter(models.GameRoom.room_code == normalized)
                .first()
            )
            if not room:
                return
            if room.game_type not in {"dice", "gomoku"}:
                return
            row = (
                db.query(models.GameState)
                .filter(models.GameState.room_id == room.id)
                .first()
            )
            if row:
                row.game_type = room.game_type
                row.state = deepcopy(state)
                row.updated_at = datetime.now()
            else:
                row = models.GameState(
                    room_id=room.id,
                    game_type=room.game_type,
                    state=deepcopy(state),
                    updated_at=datetime.now(),
                )
                db.add(row)
            try:
                db.commit()
            except IntegrityError:
                # A second process may have inserted the unique room row after
                # our read. Update that row instead of losing the snapshot.
                db.rollback()
                existing = (
                    db.query(models.GameState)
                    .filter(models.GameState.room_id == room.id)
                    .first()
                )
                if not existing:
                    raise
                existing.game_type = room.game_type
                existing.state = deepcopy(state)
                existing.updated_at = datetime.now()
                db.commit()


class ResilientGameStateStore(GameStateStore):
    """Use PostgreSQL as truth and memory/Redis only as acceleration layers."""

    def __init__(self):
        self.memory = MemoryGameStateStore()
        self.redis = RedisGameStateStore()
        self.database = DatabaseGameStateStore()

    def get(self, room_code: str) -> dict | None:
        # Reads are limited to room creation/recovery, so preferring the
        # durable source avoids reviving a stale Redis value after a partial
        # cache outage or a rolling deploy.
        with trace_span("game.snapshot.load", {"result": "error"}) as span:
            try:
                durable = self.database.get(room_code)
            except Exception as error:
                logger.warning(
                    "game_state_database_read_failed room_ref=%s error_type=%s",
                    opaque_log_reference("room", room_code),
                    type(error).__name__,
                )
                durable = None
            if durable:
                self.memory.set(room_code, durable)
                if state_cache.enabled:
                    self.redis.set(room_code, durable)
                set_span_attribute(span, "state.source", "postgresql")
                set_span_attribute(span, "result", "hit")
                return durable
            if state_cache.enabled:
                remote = self.redis.get(room_code)
                if remote:
                    self.memory.set(room_code, remote)
                    set_span_attribute(span, "state.source", "redis")
                    set_span_attribute(span, "result", "hit")
                    return remote
            local = self.memory.get(room_code)
            set_span_attribute(span, "state.source", "memory" if local else "none")
            set_span_attribute(span, "result", "hit" if local else "miss")
            return local

    def set(self, room_code: str, state: dict, ttl_seconds: int = 900) -> None:
        self.memory.set(room_code, state, ttl_seconds)
        try:
            self.database.set(room_code, state, ttl_seconds)
        except Exception as error:
            # A transient database incident must not disconnect both players;
            # Redis/memory retain the hot state and the next action retries.
            logger.error(
                "game_state_database_write_failed room_ref=%s error_type=%s",
                opaque_log_reference("room", room_code),
                type(error).__name__,
            )
        if state_cache.enabled:
            self.redis.set(room_code, state, ttl_seconds)


game_state_store: GameStateStore = ResilientGameStateStore()
