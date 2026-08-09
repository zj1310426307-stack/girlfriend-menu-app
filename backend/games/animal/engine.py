"""Pure state machine for 7×9 Animal Chess."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from games.core.engine import GameEngine, GameRuleError
from games.core.chat import append_chat

from .board import DENS, opponent
from .piece import initial_pieces
from .rule import legal_moves, validate_move


AI_ID = "ai_animal"


class AnimalGame(GameEngine):
    """Manage colors, legal moves, captures and den/no-piece victories."""

    def __init__(self, state: dict):
        self.state = deepcopy(state)

    @classmethod
    def create(cls, player_ids: list[str], names: dict[str, str] | None = None, difficulty: str = "rule"):
        """Create waiting PvP or immediately playable human-vs-AI state."""
        state = {
            "phase": "playing" if len(player_ids) == 2 else "waiting",
            "players": list(player_ids),
            "names": names or {},
            "colors": {player_id: ("blue" if index == 0 else "red") for index, player_id in enumerate(player_ids)},
            "pieces": initial_pieces(),
            "turn_id": player_ids[0] if player_ids else None,
            "winner_id": None,
            "last_move": None,
            "messages": [],
            "difficulty": difficulty,
            "round": 1,
            "started_at": datetime.now().isoformat() if len(player_ids) == 2 else None,
        }
        return cls(state)

    def add_player(self, player_id: str, name: str = "女朋友") -> dict:
        """Fill the second PvP seat without resetting the untouched board."""
        if player_id in self.state["players"]:
            return self.serialize()
        if len(self.state["players"]) >= 2 or self.state["phase"] != "waiting":
            raise GameRuleError("房间人数已满")
        self.state["players"].append(player_id)
        self.state["colors"][player_id] = "red"
        self.state["names"][player_id] = name
        self.state["phase"] = "playing"
        self.state["started_at"] = datetime.now().isoformat()
        return self.serialize()

    def move(self, player_id: str, piece_id: str, x: int, y: int) -> dict:
        """Apply one legal move and determine immediate victory conditions."""
        if self.state["phase"] != "playing" or self.state["turn_id"] != player_id:
            raise GameRuleError("现在不是你的回合")
        color = self.state["colors"].get(player_id)
        if not color:
            raise GameRuleError("玩家不属于这个房间")
        result = validate_move(self.state["pieces"], piece_id, x, y, color)
        piece, captured = result["piece"], result["target"]
        before = {"x": piece["x"], "y": piece["y"]}
        if captured:
            captured["alive"] = False
        piece["x"], piece["y"] = result["x"], result["y"]
        self.state["last_move"] = {
            "player_id": player_id,
            "piece_id": piece_id,
            "from": before,
            "to": {"x": result["x"], "y": result["y"]},
            "captured": captured["id"] if captured else None,
        }
        enemy_color = opponent(color)
        enemy_id = next(item for item in self.state["players"] if item != player_id)
        enemy_alive = any(item["alive"] and item["color"] == enemy_color for item in self.state["pieces"])
        reached_den = (piece["x"], piece["y"]) == DENS[enemy_color]
        if reached_den or not enemy_alive or not legal_moves(self.state["pieces"], enemy_color):
            self.state.update(phase="finished", winner_id=player_id, turn_id=None)
        else:
            self.state["turn_id"] = enemy_id
        return self.serialize()

    def apply(self, player_id: str, action: str, data: dict[str, Any] | None = None) -> dict:
        """Dispatch move, resignation or bounded room chat."""
        data = data or {}
        if action == "MOVE":
            return self.move(player_id, str(data.get("piece_id", "")), int(data.get("x", -1)), int(data.get("y", -1)))
        if action == "RESIGN":
            if player_id not in self.state["players"]:
                raise GameRuleError("玩家不属于这个房间")
            self.state.update(
                phase="finished",
                winner_id=next(item for item in self.state["players"] if item != player_id),
                turn_id=None,
            )
            return self.serialize()
        if action == "CHAT":
            append_chat(self.state, player_id, data.get("text", ""))
            return self.serialize()
        raise GameRuleError("不支持的斗兽棋动作")

    def serialize(self) -> dict:
        """Return a JSON-safe defensive copy."""
        return deepcopy(self.state)

    def public_state(self, viewer_id: str) -> dict:
        """Animal Chess has no hidden board information."""
        return self.serialize()
