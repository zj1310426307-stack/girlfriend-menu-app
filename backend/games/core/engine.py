"""Contracts implemented by every V2.5 turn-based game engine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GameRuleError(ValueError):
    """A safe user-facing rule violation raised by a game engine."""


class GameEngine(ABC):
    """Minimal pure-state interface shared by landlord and jungle chess."""

    @abstractmethod
    def apply(self, player_id: str, action: str, data: dict[str, Any] | None = None) -> dict:
        """Validate and apply one player action, then return a JSON-safe snapshot."""

    @abstractmethod
    def serialize(self) -> dict:
        """Return a defensive JSON-safe copy of the complete authoritative state."""

    @abstractmethod
    def public_state(self, viewer_id: str) -> dict:
        """Return a viewer-filtered snapshot that does not expose hidden information."""
