"""Process-local real-time game runtime package."""

from game_runtime.manager import (
    GameRoomManager,
    dice_room_manager,
    game_room_manager,
)


__all__ = ["GameRoomManager", "dice_room_manager", "game_room_manager"]
