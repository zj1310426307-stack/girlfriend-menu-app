"""Server-side Gomoku opponent used by the solo training mode."""
from __future__ import annotations

from collections import OrderedDict
import random

from ai.base import AIPlayer


class GomokuAI(AIPlayer):
    """Choose a legal move using wins, blocks and local line potential.

    ``random`` keeps the game relaxed. ``rule`` and ``strategy`` first finish
    immediate wins, then block immediate losses, before evaluating nearby
    cells. The engine remains authoritative; this class never mutates state.
    """

    def __init__(self, level: str = "rule"):
        super().__init__(level)
        self._action_cache: OrderedDict[tuple, tuple[int, int]] = OrderedDict()

    @staticmethod
    def _line_profiles(
        board: list[list[int]], x: int, y: int, color: int
    ) -> list[tuple[int, int]]:
        """Return hypothetical line length/open ends in all four directions."""
        size = len(board)
        profiles = []
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            length = 1
            open_ends = 0
            for direction in (-1, 1):
                step = 1
                while True:
                    nx, ny = x + dx * step * direction, y + dy * step * direction
                    if not (0 <= nx < size and 0 <= ny < size):
                        break
                    if board[ny][nx] == color:
                        length += 1
                        step += 1
                        continue
                    if board[ny][nx] == 0:
                        open_ends += 1
                    break
            profiles.append((length, open_ends))
        return profiles

    @classmethod
    def _line_score(cls, board: list[list[int]], x: int, y: int, color: int) -> int:
        score = 0
        for length, open_ends in cls._line_profiles(board, x, y, color):
            if length >= 5:
                score += 1_000_000
            else:
                score += (10 ** length) * (open_ends + 1)
        return score

    @classmethod
    def _threat_score(cls, board: list[list[int]], x: int, y: int, color: int) -> int:
        """Reward double threats, the key tactical motif in strong Gomoku play."""
        profiles = cls._line_profiles(board, x, y, color)
        forcing = sum(
            length >= 4 and open_ends >= 1 or length == 3 and open_ends == 2
            for length, open_ends in profiles
        )
        return 90_000 if forcing >= 2 else 14_000 if forcing == 1 else 0

    @staticmethod
    def _candidate_cells(board: list[list[int]]) -> list[tuple[int, int]]:
        size = len(board)
        occupied = [(x, y) for y, row in enumerate(board) for x, value in enumerate(row) if value]
        if not occupied:
            center = size // 2
            return [(center, center)]
        candidates = set()
        for stone_x, stone_y in occupied:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    x, y = stone_x + dx, stone_y + dy
                    if 0 <= x < size and 0 <= y < size and board[y][x] == 0:
                        candidates.add((x, y))
        return sorted(candidates)

    def _cached_action(self, key: tuple) -> dict | None:
        coordinates = self._action_cache.get(key)
        if coordinates is None:
            return None
        self._action_cache.move_to_end(key)
        return {"action": "MOVE", "x": coordinates[0], "y": coordinates[1]}

    def _remember_action(self, key: tuple, x: int, y: int) -> None:
        self._action_cache[key] = (x, y)
        self._action_cache.move_to_end(key)
        while len(self._action_cache) > 256:
            self._action_cache.popitem(last=False)

    def choose_action(self, state: dict, player_id: str) -> dict:
        board = state.get("board") or []
        players = state.get("players") or []
        color_by_player = {
            item.get("id"): 1 if item.get("color") in {1, "black"} else 2
            for item in players
        }
        my_color = color_by_player.get(player_id, 2)
        opponent_color = 1 if my_color == 2 else 2
        candidates = self._candidate_cells(board)
        if not candidates:
            return {"action": "PASS"}

        if self.level == "random":
            x, y = random.choice(candidates)
            return {"action": "MOVE", "x": x, "y": y}

        cache_key = (
            self.level,
            my_color,
            tuple(tuple(int(value) for value in row) for row in board),
        )
        cached = self._cached_action(cache_key)
        if cached is not None:
            return cached

        center = len(board) // 2
        ranked = []
        for x, y in candidates:
            attack = self._line_score(board, x, y, my_color)
            defense = self._line_score(board, x, y, opponent_color)
            # Winning and blocking are absolute; otherwise favour attack while
            # retaining enough defence to avoid visibly careless moves.
            if attack >= 1_000_000:
                priority = 10_000_000 + attack
            elif defense >= 1_000_000:
                priority = 9_000_000 + defense
            else:
                if self.level == "strategy":
                    attack += self._threat_score(board, x, y, my_color)
                    defense += self._threat_score(board, x, y, opponent_color)
                attack_weight = 2.25 if self.level == "strategy" else 1.5
                defense_weight = 1.35 if self.level == "strategy" else 1.0
                priority = attack * attack_weight + defense * defense_weight - 0.4 * (
                    abs(x - center) + abs(y - center)
                )
            ranked.append((priority, x, y))

        if self.level == "strategy":
            # Search only the strongest candidates. This bounded second ply
            # catches forks while preserving the phone-game latency budget.
            top = sorted(ranked, reverse=True)[:8]
            searched = []
            for priority, x, y in top:
                board[y][x] = my_color
                reply_risk = max(
                    (
                        self._line_score(board, rx, ry, opponent_color)
                        + self._threat_score(board, rx, ry, opponent_color)
                        for rx, ry in self._candidate_cells(board)
                    ),
                    default=0,
                )
                board[y][x] = 0
                searched.append((priority - reply_risk * 0.8, x, y))
            ranked = searched

        _, x, y = max(
            ranked,
            key=lambda item: (
                item[0],
                -(abs(item[1] - center) + abs(item[2] - center)),
                -item[2],
                -item[1],
            ),
        )
        self._remember_action(cache_key, x, y)
        return {"action": "MOVE", "x": x, "y": y}
