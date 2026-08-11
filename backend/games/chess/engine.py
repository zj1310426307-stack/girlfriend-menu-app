"""Server-authoritative Chinese-chess state machine."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from games.core.chat import append_chat
from games.core.engine import GameEngine, GameRuleError

from .board import board_hash, opponent
from .move import move_notation
from .piece import initial_pieces
from .rule import in_check, legal_moves, validate_move


AI_ID = "ai_chess"
TURN_TIMEOUT_SECONDS = 5 * 60
MAX_MOVES = 300
MAX_NO_PROGRESS_MOVES = 120


def _deadline(seconds: int = TURN_TIMEOUT_SECONDS) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


class ChessGame(GameEngine):
    """Own players, turns, legal moves, checks, wins and bounded history."""

    def __init__(self, state: dict):
        self.state = deepcopy(state)
        self.state.setdefault("no_progress_moves", 0)
        self.state.setdefault("turn_timeout_seconds", TURN_TIMEOUT_SECONDS)
        self.state.setdefault("draw_reason", None)
        self.state.setdefault("result_reason", None)
        if self.state.get("phase") == "playing" and not self.state.get("turn_deadline_at"):
            self.state["turn_started_at"] = datetime.now(timezone.utc).isoformat()
            self.state["turn_deadline_at"] = _deadline(int(self.state["turn_timeout_seconds"]))

    @classmethod
    def create(cls, player_ids: list[str], names: dict[str, str] | None = None, difficulty: str = "rule"):
        """Create a waiting couple game or an immediate AI training game."""
        now = datetime.now().isoformat()
        pieces = initial_pieces()
        playing = len(player_ids) == 2
        state = {
            "phase": "playing" if playing else "waiting",
            "players": list(player_ids),
            "names": names or {},
            "colors": {player_id: ("red" if index == 0 else "black") for index, player_id in enumerate(player_ids)},
            "pieces": pieces,
            "turn_id": player_ids[0] if player_ids else None,
            "winner_id": None,
            "winner_color": None,
            "check_color": None,
            "last_move": None,
            "move_history": [],
            "move_count": 0,
            "messages": [],
            "difficulty": difficulty,
            "mode": "ai" if AI_ID in player_ids else "couple",
            "round": 1,
            "started_at": now if playing else None,
            "consecutive_checks": {},
            "position_history": [board_hash(pieces, "red")] if playing else [],
            "no_progress_moves": 0,
            "turn_started_at": datetime.now(timezone.utc).isoformat() if playing else None,
            "turn_deadline_at": _deadline() if playing else None,
            "turn_timeout_seconds": TURN_TIMEOUT_SECONDS,
            "draw_reason": None,
            "result_reason": None,
        }
        return cls(state)

    def add_player(self, player_id: str, name: str = "女朋友") -> dict:
        """Fill the black seat idempotently and start a waiting room."""
        if player_id in self.state["players"]:
            return self.serialize()
        if len(self.state["players"]) >= 2 or self.state["phase"] != "waiting":
            raise GameRuleError("房间人数已满")
        self.state["players"].append(player_id)
        self.state["colors"][player_id] = "black"
        self.state["names"][player_id] = name
        self.state["phase"] = "playing"
        self.state["started_at"] = datetime.now().isoformat()
        self.state["turn_started_at"] = datetime.now(timezone.utc).isoformat()
        self.state["turn_deadline_at"] = _deadline(int(self.state.get("turn_timeout_seconds") or TURN_TIMEOUT_SECONDS))
        self.state["position_history"] = [board_hash(self.state["pieces"], "red")]
        return self.serialize()

    def move(self, player_id: str, piece_id: str, x: int, y: int) -> dict:
        """Apply one legal move, enforce long-check policy and settle wins."""
        if self.state["phase"] != "playing" or self.state["turn_id"] != player_id:
            raise GameRuleError("现在不是你的回合")
        color = self.state["colors"].get(player_id)
        if not color:
            raise GameRuleError("玩家不属于这个房间")
        result = validate_move(self.state["pieces"], piece_id, x, y, color)
        source, captured = result["piece"], result["target"]
        previous = (source["x"], source["y"])
        enemy_color = opponent(color)
        checking = in_check(result["pieces"], enemy_color)
        check_counts = dict(self.state.get("consecutive_checks") or {})
        next_count = int(check_counts.get(player_id, 0)) + 1 if checking else 0
        if checking and next_count >= 3:
            raise GameRuleError("不能连续长将三次，请换一种走法")
        check_counts[player_id] = next_count
        self.state["pieces"] = result["pieces"]
        self.state["move_count"] += 1
        self.state["no_progress_moves"] = (
            0
            if captured or source["kind"] == "pawn"
            else int(self.state.get("no_progress_moves") or 0) + 1
        )
        entry = {
            "number": self.state["move_count"],
            "player_id": player_id,
            "color": color,
            "piece_id": piece_id,
            "piece": source["label"],
            "kind": source["kind"],
            "from": {"x": previous[0], "y": previous[1]},
            "to": {"x": x, "y": y},
            "captured": captured["id"] if captured else None,
            "notation": move_notation(source, previous, (x, y)),
            "check": checking,
        }
        self.state["last_move"] = entry
        self.state["move_history"].append(entry)
        self.state["move_history"] = self.state["move_history"][-300:]
        self.state["consecutive_checks"] = check_counts
        history = list(self.state.get("position_history") or [])
        position = board_hash(self.state["pieces"], enemy_color)
        history.append(position)
        self.state["position_history"] = history[-300:]
        enemy_id = next(item for item in self.state["players"] if item != player_id)
        enemy_king_alive = any(piece["alive"] and piece["color"] == enemy_color and piece["kind"] == "king" for piece in self.state["pieces"])
        enemy_moves = legal_moves(self.state["pieces"], enemy_color) if enemy_king_alive else []
        if not enemy_king_alive or not enemy_moves:
            self.state.update(
                phase="finished",
                winner_id=player_id,
                winner_color=color,
                turn_id=None,
                result_reason="checkmate_or_king_capture",
                turn_deadline_at=None,
            )
        else:
            draw_reason = None
            if history.count(position) >= 3:
                draw_reason = "threefold_repetition"
            elif self.state["no_progress_moves"] >= MAX_NO_PROGRESS_MOVES:
                draw_reason = "no_progress_limit"
            elif self.state["move_count"] >= MAX_MOVES:
                draw_reason = "move_limit"
            if draw_reason:
                self.state.update(
                    phase="finished",
                    winner_id=None,
                    winner_color=None,
                    turn_id=None,
                    check_color=None,
                    draw_reason=draw_reason,
                    result_reason="draw",
                    turn_deadline_at=None,
                )
            else:
                self.state["turn_id"] = enemy_id
                self.state["check_color"] = enemy_color if checking else None
                self.state["turn_started_at"] = datetime.now(timezone.utc).isoformat()
                self.state["turn_deadline_at"] = _deadline(int(self.state.get("turn_timeout_seconds") or TURN_TIMEOUT_SECONDS))
        return self.serialize()

    def expire_turn(self, now: datetime | None = None) -> bool:
        """Finish a stalled match using the durable per-turn deadline."""
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
            winner_color=self.state["colors"].get(winner),
            turn_id=None,
            timed_out_player_id=timed_out,
            result_reason="turn_timeout",
            turn_deadline_at=None,
        )
        return True

    def apply(self, player_id: str, action: str, data: dict[str, Any] | None = None) -> dict:
        """Dispatch move, resignation or room chat through one game contract."""
        data = data or {}
        if action == "MOVE":
            return self.move(player_id, str(data.get("piece_id", "")), int(data.get("x", -1)), int(data.get("y", -1)))
        if action == "RESIGN":
            if player_id not in self.state["players"] or self.state["phase"] != "playing":
                raise GameRuleError("当前不能认输")
            winner = next(item for item in self.state["players"] if item != player_id)
            self.state.update(
                phase="finished",
                winner_id=winner,
                winner_color=self.state["colors"][winner],
                turn_id=None,
                result_reason="resignation",
                turn_deadline_at=None,
            )
            return self.serialize()
        if action == "CHAT":
            append_chat(self.state, player_id, data.get("text", ""))
            return self.serialize()
        raise GameRuleError("不支持的象棋动作")

    def serialize(self) -> dict:
        """Return a defensive JSON-safe snapshot."""
        return deepcopy(self.state)

    def public_state(self, viewer_id: str) -> dict:
        """Return the public board and viewer's assigned color."""
        state = self.serialize()
        state["my_color"] = state.get("colors", {}).get(viewer_id)
        return state
