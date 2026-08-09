"""Common AI contract shared by current and future games."""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIPlayer(ABC):
    """A deterministic interface for pluggable random/rule/strategy AIs."""

    def __init__(self, level: str = "rule"):
        if level not in {"random", "rule", "strategy"}:
            raise ValueError("AI 难度必须是 random、rule 或 strategy")
        self.level = level

    @abstractmethod
    def choose_action(self, state: dict, player_id: str) -> dict:
        """Return one legal action for the provided authoritative state."""
