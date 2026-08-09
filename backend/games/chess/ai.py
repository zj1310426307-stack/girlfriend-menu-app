"""Deterministic-level AI choices over legal Chinese-chess moves."""
from __future__ import annotations

import random

from games.core.engine import GameRuleError

from .piece import PIECE_VALUES
from .rule import legal_moves


class ChessAI:
    """Choose a legal random or tactical rule-based move."""

    def __init__(self, difficulty: str = "rule", rng: random.Random | None = None):
        self.difficulty = difficulty
        self.rng = rng or random.Random()

    def choose_action(self, state: dict, player_id: str) -> dict:
        """Return one MOVE payload; rule mode values captures and checks."""
        color = state.get("colors", {}).get(player_id)
        moves = legal_moves(state.get("pieces", []), color) if color else []
        if not moves:
            raise GameRuleError("AI 没有合法走法")
        if self.difficulty == "random":
            selected = self.rng.choice(moves)
        else:
            scored = []
            for move in moves:
                score = PIECE_VALUES.get(move.get("capture"), 0)
                if move.get("check"):
                    score += 180
                score += self.rng.random()
                scored.append((score, move))
            selected = max(scored, key=lambda item: item[0])[1]
        return {"action": "MOVE", "piece_id": selected["piece_id"], "x": selected["x"], "y": selected["y"]}
