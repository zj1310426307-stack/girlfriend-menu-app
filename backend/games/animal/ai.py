"""Rule-oriented Animal Chess AI for single-player rooms."""
from __future__ import annotations

from copy import deepcopy
import random

from ai.base import AIPlayer

from .board import DENS, opponent, piece_at
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
            target_den = DENS[opponent(color)]
            own_den = DENS[color]

            def evaluate(item: dict) -> tuple[float, float]:
                pieces = deepcopy(state["pieces"])
                moved = next(piece for piece in pieces if piece["id"] == item["piece_id"])
                captured = piece_at(pieces, item["x"], item["y"])
                captured_value = captured["rank"] if captured else 0
                if captured:
                    captured["alive"] = False
                moved["x"], moved["y"] = item["x"], item["y"]
                distance = abs(item["x"] - target_den[0]) + abs(item["y"] - target_den[1])
                score = captured_value * 260 - distance * 12
                if (item["x"], item["y"]) == target_den:
                    score += 100_000
                if self.level == "strategy":
                    replies = legal_moves(pieces, opponent(color))
                    for reply in replies:
                        if (reply["x"], reply["y"]) == own_den:
                            score -= 80_000
                        if reply["capture"] and (reply["x"], reply["y"]) == (moved["x"], moved["y"]):
                            score -= moved["rank"] * 320
                    # Mobility keeps stronger play from walking valuable pieces
                    # into dead ends while still advancing toward the den.
                    score += len(legal_moves(pieces, color)) * 2
                return score, random.random()

            move = max(moves, key=evaluate)
        return {"action": "MOVE", **{key: move[key] for key in ("piece_id", "x", "y")}}
