"""Latency regressions for the first real-time game state."""

import asyncio
import time

from realtime import GameRoomManager


class RecordingSocket:
    def __init__(self, events):
        self.events = events

    async def send_json(self, payload):
        self.events.append(("state", payload["type"]))


def test_join_sends_first_state_before_durable_snapshot(monkeypatch):
    """A slow durable mirror must not hold the first renderable packet."""
    events = []

    def persist(room_code, snapshot, ttl_seconds=900):
        events.append(("persist", room_code, ttl_seconds, snapshot["phase"]))

    monkeypatch.setattr("realtime.game_state_store.set", persist)

    async def scenario():
        manager = GameRoomManager()
        await manager.create_room("FAST01", "dice", 2)
        joined, message = await manager.join(
            "FAST01",
            "gf_fast_first",
            "玩家一",
            RecordingSocket(events),
            game_type="dice",
        )
        assert joined is True
        assert message == ""

    asyncio.run(scenario())
    assert events[0] == ("state", "state")
    assert events[1][0] == "persist"


def test_move_broadcast_is_not_blocked_by_slow_durable_snapshot(monkeypatch):
    """A slow production database mirror must not delay the opponent's move."""
    events = []

    def persist(room_code, snapshot, ttl_seconds=900):
        events.append(("persist_started", snapshot["state_version"]))
        time.sleep(0.2)
        events.append(("persist_finished", snapshot["state_version"]))

    monkeypatch.setattr("realtime.game_state_store.set", persist)

    async def scenario():
        manager = GameRoomManager()
        await manager.create_room("FAST02", "gomoku", 2)
        first = RecordingSocket(events)
        second = RecordingSocket(events)
        await manager.join(
            "FAST02",
            "gf_fast_black",
            "玩家一",
            first,
            game_type="gomoku",
        )
        await manager.join(
            "FAST02",
            "gf_fast_white",
            "玩家二",
            second,
            game_type="gomoku",
        )
        await manager.flush_persistence("FAST02")
        events.clear()

        started = time.perf_counter()
        assert await manager.handle(
            "FAST02",
            "gf_fast_black",
            {"type": "MOVE", "game": "gomoku", "data": {"x": 7, "y": 7}},
        ) is None
        elapsed = time.perf_counter() - started
        assert elapsed < 0.1
        assert events[:2] == [("state", "state"), ("state", "state")]
        await manager.flush_persistence("FAST02")
        assert events[-1][0] == "persist_finished"

    asyncio.run(scenario())
