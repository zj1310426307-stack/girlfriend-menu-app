"""Game Center V3 lifecycle, adapter and AI architecture guardrails."""

from __future__ import annotations

from ai.registry import AI_PROVIDERS
from games.core.lifecycle import GameStateAdapter, LifecycleOperation
from games.registry import GAME_PLUGINS


def test_every_game_declares_the_complete_lifecycle() -> None:
    """Keep create-to-replay support explicit for all preserved catalogue games."""
    for plugin in GAME_PLUGINS.all():
        assert set(plugin.lifecycle) == set(LifecycleOperation)
        assert plugin.supports(LifecycleOperation.RECOVER)
        assert plugin.supports(LifecycleOperation.REPLAY)


def test_manifest_exposes_one_state_adapter_per_game() -> None:
    """Prevent callers from rediscovering state ownership with type branches."""
    manifest = {item["game_type"]: item for item in GAME_PLUGINS.manifest()}
    assert manifest["dice"]["state_adapter"] == GameStateAdapter.REALTIME_ROOM
    assert manifest["gomoku"]["transports"] == ["http", "websocket"]
    assert manifest["aeroplane"]["state_adapter"] == GameStateAdapter.FLIGHT_STATE
    assert manifest["landlord"]["state_adapter"] == GameStateAdapter.VERSIONED_SESSION


def test_every_declared_ai_game_resolves_through_the_shared_registry() -> None:
    """Keep local game decisions out of LLM and per-route dispatch paths."""
    for plugin in GAME_PLUGINS.all():
        if plugin.ai_levels:
            provider = AI_PROVIDERS.resolve(plugin.game_type)
            assert provider.levels == plugin.ai_levels
            assert provider.decision_budget_ms <= 100
