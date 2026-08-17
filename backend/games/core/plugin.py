"""Framework-free contracts for discoverable LoveOS game plugins."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

from .engine import GameEngine


EngineFactory = Callable[[dict], GameEngine]


@dataclass(frozen=True, slots=True)
class GamePlugin:
    """Describe one stable game type without importing web or persistence code."""

    game_type: str
    name: str
    icon: str
    max_players: int
    aliases: tuple[str, ...] = ()
    modes: tuple[str, ...] = ("couple",)
    ai_levels: tuple[str, ...] = ()
    realtime: bool = True
    replay: bool = True
    engine_factory: EngineFactory | None = None
    legacy_api_prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject ambiguous descriptors before application startup."""
        if not self.game_type or self.game_type != self.game_type.strip().lower():
            raise ValueError("game_type 必须是非空小写标识")
        if self.max_players < 1:
            raise ValueError("max_players 必须大于零")
        identifiers = (self.game_type, *self.aliases)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"游戏 {self.game_type} 的别名重复")

    def restore_engine(self, state: dict) -> GameEngine:
        """Restore the plugin's pure engine or explain its legacy adapter boundary."""
        if self.engine_factory is None:
            raise LookupError(f"游戏 {self.game_type} 当前通过兼容 adapter 管理状态")
        engine = self.engine_factory(state)
        if not isinstance(engine, GameEngine):
            raise TypeError(f"游戏 {self.game_type} 的 engine_factory 未返回 GameEngine")
        return engine

    def catalog_item(self) -> dict[str, str]:
        """Return the stable database seed projection for this plugin."""
        return {
            "name": self.name,
            "icon": self.icon,
            "type": self.game_type,
            "status": "available",
        }


class GamePluginRegistry:
    """Resolve canonical game types and legacy aliases from one immutable registry."""

    def __init__(self, plugins: Iterable[GamePlugin]):
        by_type: dict[str, GamePlugin] = {}
        aliases: dict[str, str] = {}
        for plugin in plugins:
            if plugin.game_type in by_type or plugin.game_type in aliases:
                raise ValueError(f"游戏标识重复：{plugin.game_type}")
            by_type[plugin.game_type] = plugin
            for alias in plugin.aliases:
                normalized = alias.strip().lower()
                if not normalized or normalized in by_type or normalized in aliases:
                    raise ValueError(f"游戏别名重复：{alias}")
                aliases[normalized] = plugin.game_type
        self._plugins: Mapping[str, GamePlugin] = MappingProxyType(by_type)
        self._aliases: Mapping[str, str] = MappingProxyType(aliases)

    def resolve(self, game_type: str) -> GamePlugin:
        """Return a plugin for a canonical type or compatibility alias."""
        normalized = str(game_type).strip().lower()
        canonical = self._aliases.get(normalized, normalized)
        try:
            return self._plugins[canonical]
        except KeyError as error:
            raise LookupError(f"未注册的游戏类型：{game_type}") from error

    def canonical_type(self, game_type: str) -> str:
        """Normalize a public or legacy identifier to its durable catalogue type."""
        return self.resolve(game_type).game_type

    def all(self) -> tuple[GamePlugin, ...]:
        """Return plugins in deterministic registration order."""
        return tuple(self._plugins.values())


__all__ = ["EngineFactory", "GamePlugin", "GamePluginRegistry"]
