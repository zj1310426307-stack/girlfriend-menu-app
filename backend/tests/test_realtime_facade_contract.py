"""Round 3 compatibility checks for the split real-time boundaries."""

import game_runtime
import realtime
import realtime_events


def test_realtime_facade_preserves_singleton_identity():
    """Old imports must resolve to the exact new boundary singletons."""
    assert realtime.game_room_manager is game_runtime.game_room_manager
    assert realtime.dice_room_manager is game_runtime.game_room_manager
    assert realtime.order_event_hub is realtime_events.order_event_hub
    assert realtime.GameRoomManager is game_runtime.GameRoomManager
    assert realtime.OrderEventHub is realtime_events.OrderEventHub
