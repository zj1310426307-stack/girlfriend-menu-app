"""Shared room, player and versioned-state primitives for turn-based games."""

from .engine import GameEngine, GameRuleError
from .plugin import GamePlugin, GamePluginRegistry

__all__ = ["GameEngine", "GamePlugin", "GamePluginRegistry", "GameRuleError"]
