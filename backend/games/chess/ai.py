"""Deterministic-level AI choices over legal Chinese-chess moves."""
from __future__ import annotations

import random

from games.core.engine import GameRuleError

from .board import opponent
from .piece import PIECE_VALUES
from .rule import in_check, legal_moves, validate_move


class ChessAI:
    """Choose a legal move with random, tactical or shallow-search strength."""

    def __init__(self, difficulty: str = "rule", rng: random.Random | None = None):
        if difficulty not in {"random", "rule", "strategy"}:
            raise ValueError("AI 难度必须是 random、rule 或 strategy")
        self.difficulty = difficulty
        self.rng = rng or random.Random()

    @staticmethod
    def _position_value(piece: dict) -> int:
        """Small positional terms keep equal-material play purposeful."""
        if not piece["alive"]:
            return 0
        value = PIECE_VALUES[piece["kind"]]
        if piece["kind"] == "pawn":
            progress = (9 - piece["y"]) if piece["color"] == "red" else piece["y"]
            value += progress * 9
            if progress >= 5:
                value += 35
        elif piece["kind"] in {"horse", "cannon"}:
            value += 12 - abs(piece["x"] - 4) * 3
        return value

    @classmethod
    def _evaluate(cls, pieces: list[dict], color: str) -> int:
        own = sum(cls._position_value(piece) for piece in pieces if piece["color"] == color)
        enemy = sum(cls._position_value(piece) for piece in pieces if piece["color"] != color)
        score = own - enemy
        if in_check(pieces, opponent(color)):
            score += 160
        if in_check(pieces, color):
            score -= 240
        return score

    @staticmethod
    def _after(pieces: list[dict], color: str, move: dict) -> list[dict]:
        return validate_move(
            pieces,
            move["piece_id"],
            move["x"],
            move["y"],
            color,
        )["pieces"]

    def choose_action(self, state: dict, player_id: str) -> dict:
        """Return one MOVE payload; rule mode values captures and checks."""
        color = state.get("colors", {}).get(player_id)
        moves = legal_moves(state.get("pieces", []), color) if color else []
        if not moves:
            raise GameRuleError("AI 没有合法走法")
        if self.difficulty == "random":
            selected = self.rng.choice(moves)
            return {"action": "MOVE", "piece_id": selected["piece_id"], "x": selected["x"], "y": selected["y"]}

        scored = []
        enemy_color = opponent(color)
        for move in moves:
            next_pieces = self._after(state.get("pieces", []), color, move)
            score = self._evaluate(next_pieces, color)
            score += PIECE_VALUES.get(move.get("capture"), 0) * 2
            if move.get("check"):
                score += 180
            if self.difficulty == "strategy":
                replies = legal_moves(next_pieces, enemy_color)
                # A bounded two-ply search is strong enough for a phone game
                # while keeping the Render request latency predictable.
                ordered = sorted(
                    replies,
                    key=lambda reply: (
                        PIECE_VALUES.get(reply.get("capture"), 0),
                        bool(reply.get("check")),
                    ),
                    reverse=True,
                )[:18]
                if ordered:
                    score = min(
                        score,
                        min(
                            self._evaluate(self._after(next_pieces, enemy_color, reply), color)
                            for reply in ordered
                        ),
                    )
            scored.append((score + self.rng.random(), move))
        selected = max(scored, key=lambda item: item[0])[1]
        return {"action": "MOVE", "piece_id": selected["piece_id"], "x": selected["x"], "y": selected["y"]}
