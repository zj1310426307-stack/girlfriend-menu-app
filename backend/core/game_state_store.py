"""Replaceable hot-state boundary for single-instance memory or Redis deployments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
import time

from core.cache import state_cache


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


class ResilientGameStateStore(GameStateStore):
    """Keep a local copy and mirror to Redis when a configured instance is healthy."""

    def __init__(self):
        self.memory = MemoryGameStateStore()
        self.redis = RedisGameStateStore()

    def get(self, room_code: str) -> dict | None:
        if state_cache.enabled:
            remote = self.redis.get(room_code)
            if remote:
                self.memory.set(room_code, remote)
                return remote
        return self.memory.get(room_code)

    def set(self, room_code: str, state: dict, ttl_seconds: int = 900) -> None:
        self.memory.set(room_code, state, ttl_seconds)
        if state_cache.enabled:
            self.redis.set(room_code, state, ttl_seconds)


game_state_store: GameStateStore = ResilientGameStateStore()
