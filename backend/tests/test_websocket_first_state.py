"""Latency regressions for the first real-time game state."""

import asyncio

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
