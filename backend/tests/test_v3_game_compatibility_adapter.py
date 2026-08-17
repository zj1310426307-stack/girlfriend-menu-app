"""V3 game adapters preserve old recovery paths while fixing canonical aliases."""

import asyncio
from types import SimpleNamespace

from services import game_compatibility_service


def test_unknown_persisted_game_keeps_the_safe_reconnect_fallback() -> None:
    """Avoid crashing old data even when no V3 plugin has been installed for it."""
    room = SimpleNamespace(
        room_code="LEGACY",
        game_type="legacy_custom",
        status="waiting",
        max_players=2,
    )
    payload = asyncio.run(
        game_compatibility_service.recover_game_state(
            SimpleNamespace(),
            room,
            "player",
        )
    )
    assert payload == {
        "room_code": "LEGACY",
        "game_type": "legacy_custom",
        "room_status": "waiting",
        "reconnect_required": True,
    }


def test_jungle_recovery_uses_the_versioned_session_adapter(monkeypatch) -> None:
    """Map the durable jungle type that the former route condition omitted."""
    room = SimpleNamespace(
        room_code="JUNGLE",
        game_type="jungle",
        status="playing",
        max_players=2,
    )
    expected = {"room_code": "JUNGLE", "state": {"phase": "playing"}}
    monkeypatch.setattr(
        game_compatibility_service.animal_service,
        "get_any_state",
        lambda db, room_code, player_id: expected,
    )
    payload = asyncio.run(
        game_compatibility_service.recover_game_state(
            SimpleNamespace(),
            room,
            "player",
        )
    )
    assert payload is expected
