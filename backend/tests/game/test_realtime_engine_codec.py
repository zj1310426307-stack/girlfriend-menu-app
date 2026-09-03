"""Game Center V3 real-time engine codec recovery contracts."""

from __future__ import annotations

import pytest

from game_runtime.engine_codec import get_realtime_engine_codec, get_room_engine_codec


def test_gomoku_codec_round_trips_authoritative_engine_state() -> None:
    """Preserve board, players and turn data through a reconnect snapshot."""
    codec = get_realtime_engine_codec("gomoku")
    room = codec.new_room_fields()
    room["gomoku"].add_player("one")
    room["gomoku"].add_player("two")
    room["gomoku"].move("one", 7, 7)
    raw = codec.snapshot_engine(room)

    restored = codec.new_room_fields()
    codec.restore_engine(restored, raw)
    assert restored["gomoku"].serialize() == raw


def test_realtime_codec_resolves_aliases_and_rejects_http_sessions() -> None:
    """Use plugin state ownership instead of accepting arbitrary game types."""
    assert get_realtime_engine_codec("dice").game_type == "dice"
    with pytest.raises(LookupError, match="不使用实时房间状态"):
        get_realtime_engine_codec("flight")
    assert get_room_engine_codec("flight").game_type == "aeroplane"
    assert get_room_engine_codec("flight").snapshot_engine({}) is None
