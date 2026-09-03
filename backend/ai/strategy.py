"""Shared AI provider and timed-decision contracts for local game strategies."""

from __future__ import annotations

from dataclasses import dataclass
import time
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, Protocol


AI_LEVELS = ("random", "rule", "strategy")


class LocalAIStrategy(Protocol):
    """Describe the only behavior required from an in-process game AI."""

    def choose_action(self, state: dict, player_id: str) -> dict:
        """Return one server-valid action without network access."""


AIFactory = Callable[[str], LocalAIStrategy]


@dataclass(frozen=True, slots=True)
class AIPersona:
    """Describe one public difficulty persona stored in the database catalogue."""

    level: str
    name: str
    style: str


@dataclass(frozen=True, slots=True)
class AIProvider:
    """Bind one game type and its compatibility aliases to a local AI factory."""

    game_type: str
    factory: AIFactory
    levels: tuple[str, ...] = AI_LEVELS
    aliases: tuple[str, ...] = ()
    personas: tuple[AIPersona, ...] = ()
    decision_budget_ms: float = 100.0

    def __post_init__(self) -> None:
        """Validate difficulty metadata once during registry construction."""
        if not self.levels or any(level not in AI_LEVELS for level in self.levels):
            raise ValueError(f"游戏 {self.game_type} 声明了不支持的 AI 难度")
        if any(persona.level not in self.levels for persona in self.personas):
            raise ValueError(f"游戏 {self.game_type} 的 AI 人设与能力不一致")
        if self.decision_budget_ms <= 0:
            raise ValueError(f"游戏 {self.game_type} 的 AI 时延预算必须大于零")

    def create(self, level: str) -> LocalAIStrategy:
        """Create a local strategy after validating the selected level."""
        if level not in self.levels:
            raise ValueError(f"游戏 {self.game_type} 不支持 AI 难度 {level}")
        strategy = self.factory(level)
        if not callable(getattr(strategy, "choose_action", None)):
            raise TypeError(f"游戏 {self.game_type} 的 AI 未实现 choose_action")
        return strategy


@dataclass(frozen=True, slots=True)
class AIDecision:
    """Carry an action with low-cardinality performance evidence."""

    game_type: str
    level: str
    action: dict
    duration_ms: float
    budget_ms: float

    @property
    def within_budget(self) -> bool:
        """Report latency compliance without changing the chosen game action."""
        return self.duration_ms <= self.budget_ms


class AIProviderRegistry:
    """Resolve every game AI through one deterministic, network-free registry."""

    def __init__(self, providers: Iterable[AIProvider]):
        by_type: dict[str, AIProvider] = {}
        aliases: dict[str, str] = {}
        for provider in providers:
            if provider.game_type in by_type or provider.game_type in aliases:
                raise ValueError(f"AI 游戏标识重复：{provider.game_type}")
            by_type[provider.game_type] = provider
            for alias in provider.aliases:
                normalized = alias.strip().lower()
                if not normalized or normalized in by_type or normalized in aliases:
                    raise ValueError(f"AI 游戏别名重复：{alias}")
                aliases[normalized] = provider.game_type
        self._providers: Mapping[str, AIProvider] = MappingProxyType(by_type)
        self._aliases: Mapping[str, str] = MappingProxyType(aliases)
        self._strategies: dict[tuple[str, str], LocalAIStrategy] = {}

    def resolve(self, game_type: str) -> AIProvider:
        """Resolve a canonical game type or stable compatibility alias."""
        normalized = str(game_type).strip().lower()
        canonical = self._aliases.get(normalized, normalized)
        try:
            return self._providers[canonical]
        except KeyError as error:
            raise LookupError(f"游戏 {game_type} 没有本地 AI") from error

    def choose_action(
        self,
        game_type: str,
        state: dict,
        player_id: str,
        level: str = "rule",
    ) -> AIDecision:
        """Measure one in-process decision while preserving its action payload."""
        provider = self.resolve(game_type)
        strategy_key = (provider.game_type, level)
        strategy = self._strategies.get(strategy_key)
        if strategy is None:
            strategy = provider.create(level)
            self._strategies[strategy_key] = strategy
        started = time.perf_counter()
        action = strategy.choose_action(state, player_id)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        if not isinstance(action, dict) or not action.get("action"):
            raise TypeError(f"游戏 {provider.game_type} 的 AI 返回了无效动作")
        return AIDecision(
            provider.game_type,
            level,
            action,
            duration_ms,
            provider.decision_budget_ms,
        )

    def providers(self) -> tuple[AIProvider, ...]:
        """Return providers in deterministic registration order."""
        return tuple(self._providers.values())

    def persona_catalog(self) -> tuple[tuple[str, str, str, dict], ...]:
        """Project existing public AI personas for idempotent database seeding."""
        return tuple(
            (provider.game_type, persona.level, persona.name, {"style": persona.style})
            for provider in self._providers.values()
            for persona in provider.personas
        )

    def manifest(self) -> tuple[dict, ...]:
        """Return low-cardinality AI capabilities for architecture audits."""
        return tuple(
            {
                "game_type": provider.game_type,
                "aliases": list(provider.aliases),
                "levels": list(provider.levels),
                "decision_budget_ms": provider.decision_budget_ms,
            }
            for provider in self._providers.values()
        )


__all__ = [
    "AI_LEVELS",
    "AIDecision",
    "AIFactory",
    "AIPersona",
    "AIProvider",
    "AIProviderRegistry",
    "LocalAIStrategy",
]
