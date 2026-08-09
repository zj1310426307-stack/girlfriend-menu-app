"""Pure, JSON-serializable rules engine for the V2.4 couple flight game.

The database/service layer owns identity, random dice generation and rewards.
This module owns only deterministic board rules so it can be tested without IO.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime


PIECES_PER_PLAYER = 4
TRACK_LENGTH = 28
HOME_STRETCH_START = 28
FINISH_POSITION = 32
EVENT_SQUARES = {
    4: "LOVE",
    8: "FOOD",
    12: "FUN",
    16: "TASK",
    20: "LOVE",
    24: "FOOD",
    29: "FUN",
}
COLORS = ("red", "blue")
START_OFFSETS = (0, 14)


class FlightError(ValueError):
    """Base error for a rejected game action."""


class InvalidPhase(FlightError):
    pass


class NotYourTurn(FlightError):
    pass


class InvalidAction(FlightError):
    pass


class InvalidPiece(FlightError):
    pass


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def initial_state(players: list[dict] | None = None) -> dict:
    normalized = []
    for index, player in enumerate((players or [])[:2]):
        normalized.append(
            {
                "id": str(player["id"]),
                "name": str(player.get("name") or f"玩家{index + 1}"),
                "seat": int(player.get("seat") or index + 1),
                "color": COLORS[index],
            }
        )
    playing = len(normalized) == 2
    return {
        "version": 1,
        "phase": "playing" if playing else "waiting",
        "round": 1,
        "players": normalized,
        "pieces": {player["id"]: [-1] * PIECES_PER_PLAYER for player in normalized},
        "turn_id": normalized[0]["id"] if playing else None,
        "dice": None,
        "movable": [],
        "winner_id": None,
        "last_action": None,
        "pending_event": None,
        "started_at": _now_iso() if playing else None,
        "event_sequence": 0,
        "move_history": [],
    }


class FlightGame:
    def __init__(self, state: dict | None = None):
        self.state = deepcopy(state) if state else initial_state()
        self._validate_state()

    def _validate_state(self):
        players = self.state.get("players") or []
        if len(players) > 2:
            raise InvalidAction("飞行棋房间最多两名玩家")
        self.state.setdefault("pieces", {})
        self.state.setdefault("event_sequence", 0)
        self.state.setdefault("move_history", [])
        for player in players:
            pieces = self.state["pieces"].setdefault(player["id"], [-1] * PIECES_PER_PLAYER)
            if len(pieces) != PIECES_PER_PLAYER:
                raise InvalidAction("每位玩家必须有四颗棋子")

    def serialize(self) -> dict:
        return deepcopy(self.state)

    def _record_last_action(self) -> None:
        """Keep a bounded, JSON-safe server replay for V2.7."""
        if self.state.get("last_action"):
            self.state["move_history"].append(
                {**deepcopy(self.state["last_action"]), "number": len(self.state["move_history"]) + 1}
            )
            self.state["move_history"] = self.state["move_history"][-500:]

    def sync_players(self, players: list[dict]) -> dict:
        """Merge persisted room seats into the board and start at two players."""
        if self.state["phase"] == "finished":
            return self.serialize()
        known = {player["id"] for player in self.state["players"]}
        for index, player in enumerate(players[:2]):
            player_id = str(player["id"])
            if player_id not in known:
                self.state["players"].append(
                    {
                        "id": player_id,
                        "name": str(player.get("name") or f"玩家{index + 1}"),
                        "seat": int(player.get("seat") or index + 1),
                        "color": COLORS[len(self.state["players"])],
                    }
                )
                self.state["pieces"][player_id] = [-1] * PIECES_PER_PLAYER
                known.add(player_id)
        self.state["players"].sort(key=lambda item: item["seat"])
        for index, player in enumerate(self.state["players"]):
            player["color"] = COLORS[index]
        if len(self.state["players"]) == 2 and self.state["phase"] == "waiting":
            self.state["phase"] = "playing"
            self.state["turn_id"] = self.state["players"][0]["id"]
            self.state["started_at"] = _now_iso()
            self.state["last_action"] = {"type": "START", "player_id": self.state["turn_id"]}
            self._record_last_action()
        return self.serialize()

    def _require_turn(self, player_id: str):
        if self.state["phase"] != "playing":
            raise InvalidPhase("游戏尚未开始或已经结束")
        if player_id != self.state["turn_id"]:
            raise NotYourTurn("还没轮到你")

    def _next_player(self):
        players = self.state["players"]
        current = next(index for index, player in enumerate(players) if player["id"] == self.state["turn_id"])
        self.state["turn_id"] = players[(current + 1) % len(players)]["id"]

    @staticmethod
    def _target(position: int, dice: int) -> int | None:
        if position == -1:
            return 0 if dice == 6 else None
        target = position + dice
        return target if target <= FINISH_POSITION else None

    def movable_pieces(self, player_id: str, dice: int) -> list[int]:
        return [
            index
            for index, position in enumerate(self.state["pieces"][player_id])
            if position != FINISH_POSITION and self._target(position, dice) is not None
        ]

    def roll_dice(self, player_id: str, dice: int) -> dict:
        self._require_turn(player_id)
        if self.state["pending_event"]:
            raise InvalidAction("请先完成当前互动任务")
        if self.state["dice"] is not None:
            raise InvalidAction("请先移动一颗棋子")
        if dice not in range(1, 7):
            raise InvalidAction("骰子点数必须在 1 到 6 之间")
        movable = self.movable_pieces(player_id, dice)
        self.state["dice"] = dice
        self.state["movable"] = movable
        self.state["last_action"] = {
            "type": "ROLL_DICE",
            "player_id": player_id,
            "dice": dice,
        }
        if not movable:
            self.state["dice"] = None
            self._next_player()
            self.state["last_action"]["passed"] = True
        self._record_last_action()
        return self.serialize()

    def _capture(self, player_id: str, target: int) -> list[dict]:
        if target >= TRACK_LENGTH:
            return []
        global_position = self._global_track_position(player_id, target)
        captured = []
        for opponent_index, opponent in enumerate(self.state["players"]):
            if opponent["id"] == player_id:
                continue
            opponent_pieces = self.state["pieces"][opponent["id"]]
            for piece_index, position in enumerate(opponent_pieces):
                if 0 <= position < TRACK_LENGTH:
                    opponent_global = (position + START_OFFSETS[opponent_index]) % TRACK_LENGTH
                    if opponent_global == global_position:
                        opponent_pieces[piece_index] = -1
                        captured.append({"player_id": opponent["id"], "piece_index": piece_index})
        return captured

    def _global_track_position(self, player_id: str, position: int) -> int:
        player_index = next(index for index, player in enumerate(self.state["players"]) if player["id"] == player_id)
        return (position + START_OFFSETS[player_index]) % TRACK_LENGTH

    def move_piece(self, player_id: str, piece_index: int) -> dict:
        self._require_turn(player_id)
        if self.state["dice"] is None:
            raise InvalidAction("请先掷骰子")
        if piece_index not in range(PIECES_PER_PLAYER):
            raise InvalidPiece("棋子编号无效")
        if piece_index not in self.state["movable"]:
            raise InvalidPiece("这颗棋子当前不能移动")
        dice = self.state["dice"]
        source = self.state["pieces"][player_id][piece_index]
        target = self._target(source, dice)
        self.state["pieces"][player_id][piece_index] = target
        captured = self._capture(player_id, target)
        self.state["dice"] = None
        self.state["movable"] = []
        self.state["last_action"] = {
            "type": "MOVE_PIECE",
            "player_id": player_id,
            "piece_index": piece_index,
            "from": source,
            "to": target,
            "dice": dice,
            "captured": captured,
        }

        if all(position == FINISH_POSITION for position in self.state["pieces"][player_id]):
            self.state["phase"] = "finished"
            self.state["winner_id"] = player_id
            self.state["turn_id"] = None
            self._record_last_action()
            return self.serialize()

        event_position = self._global_track_position(player_id, target) if target < TRACK_LENGTH else target
        event_type = EVENT_SQUARES.get(event_position)
        if event_type:
            self.state["event_sequence"] += 1
            self.state["pending_event"] = {
                "type": event_type,
                "player_id": player_id,
                "piece_index": piece_index,
                "sequence": self.state["event_sequence"],
                "extra_turn": dice == 6,
            }
            self._record_last_action()
            return self.serialize()
        if dice != 6:
            self._next_player()
        self._record_last_action()
        return self.serialize()

    def attach_event(self, event: dict) -> dict:
        if not self.state["pending_event"]:
            raise InvalidAction("当前没有待处理的互动事件")
        self.state["pending_event"].update(deepcopy(event))
        return self.serialize()

    def complete_event(self, player_id: str) -> dict:
        self._require_turn(player_id)
        event = self.state["pending_event"]
        if not event or event["player_id"] != player_id:
            raise InvalidAction("当前没有需要你完成的互动事件")
        extra_turn = bool(event.get("extra_turn"))
        self.state["last_action"] = {
            "type": "COMPLETE_EVENT",
            "player_id": player_id,
            "event": deepcopy(event),
        }
        self.state["pending_event"] = None
        if not extra_turn:
            self._next_player()
        self._record_last_action()
        return self.serialize()
