"""Server-side Gomoku opponent used by the solo training mode."""
from __future__ import annotations

import random

from ai.base import AIPlayer


class GomokuAI(AIPlayer):
    """Choose a legal move using wins, blocks and local line potential.

    ``random`` keeps the game relaxed. ``rule`` and ``strategy`` first finish
    immediate wins, then block immediate losses, before evaluating nearby
    cells. The engine remains authoritative; this class never mutates state.
    """

    @staticmethod
    def _line_score(board: list[list[int]], x: int, y: int, color: int) -> int:
        size = len(board)
        score = 0
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
            if length >= 5:
                score += 1_000_000
            else:
                score += (10 ** length) * (open_ends + 1)
        return score

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
        return list(candidates)

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
                attack_weight = 2.0 if self.level == "strategy" else 1.5
                priority = attack * attack_weight + defense - 0.4 * (
                    abs(x - center) + abs(y - center)
                )
            ranked.append((priority, random.random(), x, y))
        _, _, x, y = max(ranked)
        return {"action": "MOVE", "x": x, "y": y}
