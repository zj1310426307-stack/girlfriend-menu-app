"""Pure, serializable Gomoku rule engine.

The engine deliberately has no FastAPI, database, or WebSocket dependencies.
Room transports can therefore keep one :class:`GomokuGame` per active room,
feed validated player ids into ``move()``, and broadcast ``serialize()``.

Coordinates use the conventional screen layout: ``x`` grows from left to
right, ``y`` grows from top to bottom, and a cell is accessed as
``board[y][x]``. Board values are ``0`` (empty), ``1`` (black), and ``2``
(white).
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable


BOARD_SIZE = 15
EMPTY = 0
BLACK = 1
WHITE = 2

COLOR_NAMES = {BLACK: "black", WHITE: "white"}
COLOR_VALUES = {name: value for value, name in COLOR_NAMES.items()}


class GomokuError(Exception):
    """Base exception for a rejected Gomoku operation.

    ``code`` is stable and suitable for a WebSocket/API error envelope, while
    ``details`` carries optional machine-readable context.
    """

    code = "GOMOKU_ERROR"
    default_message = "五子棋操作失败"

    def __init__(self, message: str | None = None, **details: Any) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


class InvalidPlayerError(GomokuError):
    code = "INVALID_PLAYER"
    default_message = "玩家标识不能为空"


class PlayerAlreadyJoinedError(GomokuError):
    code = "PLAYER_ALREADY_JOINED"
    default_message = "玩家已经加入本局游戏"


class GameFullError(GomokuError):
    code = "GAME_FULL"
    default_message = "本局游戏已经有两名玩家"


class UnknownPlayerError(GomokuError):
    code = "UNKNOWN_PLAYER"
    default_message = "玩家不在本局游戏中"


class GameNotReadyError(GomokuError):
    code = "GAME_NOT_READY"
    default_message = "需要两名玩家加入后才能开始"


class GameFinishedError(GomokuError):
    code = "GAME_FINISHED"
    default_message = "本局已经结束，请重开后继续"


class NotYourTurnError(GomokuError):
    code = "NOT_YOUR_TURN"
    default_message = "还没有轮到该玩家落子"


class OutOfBoundsError(GomokuError):
    code = "OUT_OF_BOUNDS"
    default_message = "落子位置超出棋盘范围"


class OccupiedCellError(GomokuError):
    code = "OCCUPIED_CELL"
    default_message = "该位置已经有棋子"


class GomokuGame:
    """A two-player, freestyle Gomoku game on a fixed 15x15 board.

    The first joined player is black and always starts. Five or more
    consecutive stones in a horizontal, vertical, or diagonal line wins.
    """

    size = BOARD_SIZE

    def __init__(self, player_ids: Iterable[str] | None = None) -> None:
        self.players: OrderedDict[str, int] = OrderedDict()
        self.board: list[list[int]] = self._empty_board()
        self.phase = "waiting"
        self.turn_id: str | None = None
        self.winner_id: str | None = None
        self.last_move: dict[str, Any] | None = None
        self.move_count = 0
        self.move_history: list[dict[str, Any]] = []
        self.round = 1
        self.is_draw = False

        for player_id in player_ids or ():
            self.add_player(player_id)

    @staticmethod
    def _empty_board() -> list[list[int]]:
        return [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

    def add_player(self, player_id: str) -> str:
        """Add a player and return ``black`` or ``white``.

        Player ids are immutable within a game. Reconnecting transports should
        detect an existing id before calling this method instead of attempting
        to add the same player twice.
        """

        if not isinstance(player_id, str) or not player_id.strip():
            raise InvalidPlayerError()
        player_id = player_id.strip()
        if player_id in self.players:
            raise PlayerAlreadyJoinedError(player_id=player_id)
        if len(self.players) >= 2:
            raise GameFullError(player_id=player_id)

        color = BLACK if not self.players else WHITE
        self.players[player_id] = color
        if len(self.players) == 2:
            self.phase = "playing"
            self.turn_id = self._player_for_color(BLACK)
        return COLOR_NAMES[color]

    def move(self, player_id: str, x: int, y: int) -> dict[str, Any]:
        """Place one stone or raise a precise :class:`GomokuError`.

        The returned dictionary is a compact event result. Call ``serialize``
        when a full state snapshot is needed by a reconnecting client.
        """

        if player_id not in self.players:
            raise UnknownPlayerError(player_id=player_id)
        if self.phase == "waiting":
            raise GameNotReadyError()
        if self.phase == "finished":
            raise GameFinishedError(winner_id=self.winner_id, is_draw=self.is_draw)
        if player_id != self.turn_id:
            raise NotYourTurnError(player_id=player_id, turn_id=self.turn_id)
        if (
            not isinstance(x, int)
            or isinstance(x, bool)
            or not isinstance(y, int)
            or isinstance(y, bool)
            or x < 0
            or x >= BOARD_SIZE
            or y < 0
            or y >= BOARD_SIZE
        ):
            raise OutOfBoundsError(x=x, y=y, size=BOARD_SIZE)
        if self.board[y][x] != EMPTY:
            raise OccupiedCellError(x=x, y=y)

        color = self.players[player_id]
        self.board[y][x] = color
        self.move_count += 1
        self.last_move = {
            "player_id": player_id,
            "color": COLOR_NAMES[color],
            "x": x,
            "y": y,
        }
        self.move_history.append({**self.last_move, "number": self.move_count})

        if self._has_five(x, y, color):
            self.phase = "finished"
            self.winner_id = player_id
            self.turn_id = None
        elif self.move_count == BOARD_SIZE * BOARD_SIZE:
            self.phase = "finished"
            self.is_draw = True
            self.turn_id = None
        else:
            next_color = WHITE if color == BLACK else BLACK
            self.turn_id = self._player_for_color(next_color)

        return {
            "move": dict(self.last_move),
            "phase": self.phase,
            "turn_id": self.turn_id,
            "winner_id": self.winner_id,
            "is_draw": self.is_draw,
            "move_count": self.move_count,
            "round": self.round,
        }

    def reset(self) -> dict[str, Any]:
        """Start a fresh round while retaining the current player seats."""

        self.board = self._empty_board()
        self.winner_id = None
        self.last_move = None
        self.move_count = 0
        self.move_history = []
        self.is_draw = False
        self.round += 1
        if len(self.players) == 2:
            self.phase = "playing"
            self.turn_id = self._player_for_color(BLACK)
        else:
            self.phase = "waiting"
            self.turn_id = None
        return self.serialize()

    def serialize(self) -> dict[str, Any]:
        """Return a JSON-compatible, mutation-safe game snapshot."""

        winner_color = None
        if self.winner_id is not None:
            winner_color = COLOR_NAMES[self.players[self.winner_id]]
        return {
            "size": BOARD_SIZE,
            "board": [row[:] for row in self.board],
            "players": [
                {"id": player_id, "color": COLOR_NAMES[color]}
                for player_id, color in self.players.items()
            ],
            "phase": self.phase,
            "turn_id": self.turn_id,
            "winner_id": self.winner_id,
            "winner_color": winner_color,
            "last_move": dict(self.last_move) if self.last_move else None,
            "move_count": self.move_count,
            "move_history": [dict(item) for item in self.move_history],
            "is_draw": self.is_draw,
            "round": self.round,
        }

    def _player_for_color(self, color: int) -> str | None:
        return next(
            (player_id for player_id, value in self.players.items() if value == color),
            None,
        )

    def _has_five(self, x: int, y: int, color: int) -> bool:
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            length = 1
            length += self._count_direction(x, y, dx, dy, color)
            length += self._count_direction(x, y, -dx, -dy, color)
            if length >= 5:
                return True
        return False

    def _count_direction(
        self,
        x: int,
        y: int,
        dx: int,
        dy: int,
        color: int,
    ) -> int:
        count = 0
        next_x, next_y = x + dx, y + dy
        while (
            0 <= next_x < BOARD_SIZE
            and 0 <= next_y < BOARD_SIZE
            and self.board[next_y][next_x] == color
        ):
            count += 1
            next_x += dx
            next_y += dy
        return count


__all__ = [
    "BOARD_SIZE",
    "EMPTY",
    "BLACK",
    "WHITE",
    "GomokuGame",
    "GomokuError",
    "InvalidPlayerError",
    "PlayerAlreadyJoinedError",
    "GameFullError",
    "UnknownPlayerError",
    "GameNotReadyError",
    "GameFinishedError",
    "NotYourTurnError",
    "OutOfBoundsError",
    "OccupiedCellError",
]
