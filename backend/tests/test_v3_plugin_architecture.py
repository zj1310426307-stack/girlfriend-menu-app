"""V3 game and AI registries must preserve every deployed compatibility type."""

from __future__ import annotations

import pytest

from ai.registry import AI_PROVIDERS
from games.core.plugin import GamePlugin, GamePluginRegistry
from games.registry import GAME_PLUGINS
from seed import GAME_CATALOG
from services.game_persistence_service import GAME_MAX_PLAYERS


EXPECTED_GAME_TYPES = {
    "dice",
    "gomoku",
    "aeroplane",
    "landlord",
    "jungle",
    "chinese_chess",
}


def test_game_registry_is_the_catalogue_and_room_capacity_source() -> None:
    """Keep database seeds and runtime room capacities aligned with plugins."""
    registered = {plugin.game_type for plugin in GAME_PLUGINS.all()}
    assert registered == EXPECTED_GAME_TYPES
    assert {item["type"] for item in GAME_CATALOG} == EXPECTED_GAME_TYPES
    assert GAME_MAX_PLAYERS == {
        plugin.game_type: plugin.max_players for plugin in GAME_PLUGINS.all()
    }


def test_legacy_game_aliases_resolve_without_changing_durable_types() -> None:
    """Preserve public route vocabulary while using stable catalogue identifiers."""
    assert GAME_PLUGINS.canonical_type("flight") == "aeroplane"
    assert GAME_PLUGINS.canonical_type("animal") == "jungle"
    assert GAME_PLUGINS.canonical_type("chess") == "chinese_chess"
    with pytest.raises(LookupError, match="未注册"):
        GAME_PLUGINS.resolve("not-a-game")


def test_pure_engine_plugins_restore_the_existing_engine_contract() -> None:
    """Restore unified engines while legacy engines remain explicit adapters."""
    state = {
        "phase": "waiting",
        "players": ["one"],
        "names": {"one": "玩家"},
        "hands": {},
        "landlord_cards": [],
        "turn_id": None,
        "bid_index": 0,
        "bids": {},
        "landlord_id": None,
        "last_play": None,
        "pass_count": 0,
        "winner_id": None,
        "messages": [],
        "difficulty": "rule",
        "mode": "couple",
        "round": 1,
    }
    restored = GAME_PLUGINS.resolve("landlord").restore_engine(state)
    assert restored.serialize()["players"] == ["one"]
    with pytest.raises(LookupError, match="兼容 adapter"):
        GAME_PLUGINS.resolve("flight").restore_engine({})


def test_registry_rejects_duplicate_identifiers() -> None:
    """Fail startup rather than silently shadowing a game or compatibility alias."""
    with pytest.raises(ValueError, match="重复"):
        GamePluginRegistry(
            (
                GamePlugin("first", "一", "1", 2, aliases=("shared",)),
                GamePlugin("second", "二", "2", 2, aliases=("shared",)),
            )
        )


def test_ai_registry_preserves_personas_and_returns_timed_local_actions() -> None:
    """Use the unified in-process path without changing existing action payloads."""
    personas = AI_PROVIDERS.persona_catalog()
    assert len(personas) == 14
    assert ("gomoku", "strategy", "五子棋挑战者", {"style": "strategy"}) in personas
    board = [[0 for _ in range(15)] for _ in range(15)]
    decision = AI_PROVIDERS.choose_action(
        "gomoku",
        {
            "board": board,
            "players": [
                {"id": "human", "color": "black"},
                {"id": "ai_gomoku", "color": "white"},
            ],
        },
        "ai_gomoku",
        "rule",
    )
    assert decision.game_type == "gomoku"
    assert decision.action == {"action": "MOVE", "x": 7, "y": 7}
    assert decision.duration_ms >= 0
