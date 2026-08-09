"""Rule-oriented Animal Chess AI for single-player rooms."""
from __future__ import annotations

import random

from ai.base import AIPlayer

from .board import DENS
from .rule import legal_moves


class AnimalAI(AIPlayer):
    """Prefer wins and captures, then move toward the opponent den."""

    def choose_action(self, state: dict, player_id: str) -> dict:
        color = state["colors"][player_id]
        moves = legal_moves(state["pieces"], color)
        if not moves:
            return {"action": "RESIGN"}
        if self.level == "random":
            move = random.choice(moves)
        else:
            target_den = DENS["red" if color == "blue" else "blue"]
            move = sorted(
                moves,
                key=lambda item: (
                    (item["x"], item["y"]) != target_den,
                    not item["capture"],
                    abs(item["x"] - target_den[0]) + abs(item["y"] - target_den[1]),
                    item["piece_id"],
                ),
            )[0]
        return {"action": "MOVE", **{key: move[key] for key in ("piece_id", "x", "y")}}
