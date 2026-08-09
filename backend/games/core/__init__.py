"""Shared room, player and versioned-state primitives for turn-based games."""

from .engine import GameEngine, GameRuleError

__all__ = ["GameEngine", "GameRuleError"]
