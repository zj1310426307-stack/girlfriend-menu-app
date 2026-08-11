"""Pure state machine for 7×9 Animal Chess."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from games.core.engine import GameEngine, GameRuleError
from games.core.chat import append_chat

from .board import DENS, opponent
from .piece import initial_pieces
from .rule import legal_moves, validate_move


AI_ID = "ai_animal"
TURN_TIMEOUT_SECONDS = 5 * 60
MAX_MOVES = 300
MAX_NO_CAPTURE_MOVES = 100


def _position_hash(pieces: list[dict], turn_color: str) -> str:
    """Build a deterministic repetition key from live pieces and side to move."""
    values = sorted(
        f"{piece['id']}:{piece['x']}:{piece['y']}"
        for piece in pieces
        if piece["alive"]
    )
    return f"{turn_color}|" + "|".join(values)


def _deadline(seconds: int = TURN_TIMEOUT_SECONDS) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


class AnimalGame(GameEngine):
    """Manage colors, legal moves, captures and den/no-piece victories."""

    def __init__(self, state: dict):
        self.state = deepcopy(state)
        self.state.setdefault("move_count", 0)
        self.state.setdefault("no_capture_moves", 0)
        self.state.setdefault("position_history", [])
        self.state.setdefault("turn_timeout_seconds", TURN_TIMEOUT_SECONDS)
        self.state.setdefault("draw_reason", None)
        self.state.setdefault("result_reason", None)
        if self.state.get("phase") == "playing" and not self.state.get("turn_deadline_at"):
            self.state["turn_started_at"] = datetime.now(timezone.utc).isoformat()
            self.state["turn_deadline_at"] = _deadline(int(self.state["turn_timeout_seconds"]))

    @classmethod
    def create(cls, player_ids: list[str], names: dict[str, str] | None = None, difficulty: str = "rule"):
        """Create waiting PvP or immediately playable human-vs-AI state."""
        pieces = initial_pieces()
        playing = len(player_ids) == 2
        state = {
            "phase": "playing" if playing else "waiting",
            "players": list(player_ids),
            "names": names or {},
            "colors": {player_id: ("blue" if index == 0 else "red") for index, player_id in enumerate(player_ids)},
            "pieces": pieces,
            "turn_id": player_ids[0] if player_ids else None,
            "winner_id": None,
            "last_move": None,
            "messages": [],
            "difficulty": difficulty,
            "round": 1,
            "started_at": datetime.now().isoformat() if playing else None,
            "turn_started_at": datetime.now(timezone.utc).isoformat() if playing else None,
            "turn_deadline_at": _deadline() if playing else None,
            "turn_timeout_seconds": TURN_TIMEOUT_SECONDS,
            "move_count": 0,
            "no_capture_moves": 0,
            "position_history": [_position_hash(pieces, "blue")] if playing else [],
            "draw_reason": None,
            "result_reason": None,
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
        self.state["turn_started_at"] = datetime.now(timezone.utc).isoformat()
        self.state["turn_deadline_at"] = _deadline(int(self.state.get("turn_timeout_seconds") or TURN_TIMEOUT_SECONDS))
        self.state["position_history"] = [_position_hash(self.state["pieces"], "blue")]
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
        self.state["move_count"] = int(self.state.get("move_count") or 0) + 1
        self.state["no_capture_moves"] = 0 if captured else int(self.state.get("no_capture_moves") or 0) + 1
        enemy_color = opponent(color)
        enemy_id = next(item for item in self.state["players"] if item != player_id)
        enemy_alive = any(item["alive"] and item["color"] == enemy_color for item in self.state["pieces"])
        reached_den = (piece["x"], piece["y"]) == DENS[enemy_color]
        if reached_den or not enemy_alive or not legal_moves(self.state["pieces"], enemy_color):
            self.state.update(
                phase="finished",
                winner_id=player_id,
                turn_id=None,
                result_reason="den_or_no_legal_move",
                turn_deadline_at=None,
            )
        else:
            history = list(self.state.get("position_history") or [])
            position = _position_hash(self.state["pieces"], enemy_color)
            history.append(position)
            self.state["position_history"] = history[-200:]
            draw_reason = None
            if history.count(position) >= 3:
                draw_reason = "threefold_repetition"
            elif self.state["no_capture_moves"] >= MAX_NO_CAPTURE_MOVES:
                draw_reason = "no_capture_limit"
            elif self.state["move_count"] >= MAX_MOVES:
                draw_reason = "move_limit"
            if draw_reason:
                self.state.update(
                    phase="finished",
                    winner_id=None,
                    turn_id=None,
                    draw_reason=draw_reason,
                    result_reason="draw",
                    turn_deadline_at=None,
                )
            else:
                self.state["turn_id"] = enemy_id
                self.state["turn_started_at"] = datetime.now(timezone.utc).isoformat()
                self.state["turn_deadline_at"] = _deadline(int(self.state.get("turn_timeout_seconds") or TURN_TIMEOUT_SECONDS))
        return self.serialize()

    def expire_turn(self, now: datetime | None = None) -> bool:
        """Award the game to the opponent after the persisted turn deadline."""
        if self.state.get("phase") != "playing" or not self.state.get("turn_id"):
            return False
        raw = self.state.get("turn_deadline_at")
        if not raw:
            self.state["turn_deadline_at"] = _deadline(int(self.state.get("turn_timeout_seconds") or TURN_TIMEOUT_SECONDS))
            return False
        deadline = datetime.fromisoformat(raw)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current < deadline:
            return False
        timed_out = self.state["turn_id"]
        winner = next(item for item in self.state["players"] if item != timed_out)
        self.state.update(
            phase="finished",
            winner_id=winner,
            turn_id=None,
            timed_out_player_id=timed_out,
            result_reason="turn_timeout",
            turn_deadline_at=None,
        )
        return True

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
                result_reason="resignation",
                turn_deadline_at=None,
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
