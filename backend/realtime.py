"""Compatibility facade for the former combined real-time module.

New code should import order events from :mod:`realtime_events` and the game
runtime from :mod:`game_runtime`.  These exports remain stable for deployed
routers, maintenance code and third-party scripts during the modularization.
"""

from game_runtime.manager import (
    GameRoomManager,
    dice_room_manager,
    game_room_manager,
    game_state_store,
)
from realtime_events import OrderEventHub, order_event_hub


__all__ = [
    "GameRoomManager",
    "OrderEventHub",
    "dice_room_manager",
    "game_room_manager",
    "game_state_store",
    "order_event_hub",
]
