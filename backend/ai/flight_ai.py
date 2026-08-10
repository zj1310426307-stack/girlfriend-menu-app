"""Server-side move selection for solo couple-flight practice."""
from __future__ import annotations

import random

from ai.base import AIPlayer
from flight import FINISH_POSITION


class FlightAI(AIPlayer):
    """Choose one movable plane without inspecting future dice rolls."""

    def choose_action(self, state: dict, player_id: str) -> dict:
        """Implement the shared AI contract with one server-legal move."""
        return {
            "action": "MOVE_PIECE",
            "piece_index": self.choose_piece(state, player_id),
        }

    def choose_piece(self, state: dict, player_id: str) -> int:
        movable = list(state.get("movable") or [])
        if not movable:
            raise ValueError("AI 当前没有可移动棋子")
        if self.level == "random":
            return random.choice(movable)
        positions = state.get("pieces", {}).get(player_id, [])
        dice = int(state.get("dice") or 0)

        def score(index: int) -> tuple[int, int, float]:
            source = positions[index]
            target = 0 if source == -1 else source + dice
            exact_finish = int(target == FINISH_POSITION)
            launch = int(source == -1)
            # Rule AI finishes a plane first, then advances the leading plane.
            # Strategy AI spreads pieces slightly to reduce easy captures.
            spread_penalty = positions.count(source) if self.level == "strategy" else 0
            return exact_finish, launch + target - spread_penalty, random.random()

        return max(movable, key=score)


__all__ = ["FlightAI"]
