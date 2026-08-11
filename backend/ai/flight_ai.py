"""Server-side move selection for solo couple-flight practice."""
from __future__ import annotations

import random

from ai.base import AIPlayer
from flight import FINISH_POSITION, START_OFFSETS, TRACK_LENGTH


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
        players = state.get("players") or []
        player_index = next(
            (index for index, player in enumerate(players) if player.get("id") == player_id),
            0,
        )
        opponents = [
            (index, player)
            for index, player in enumerate(players)
            if player.get("id") != player_id
        ]

        def global_position(index: int, position: int) -> int | None:
            if not 0 <= position < TRACK_LENGTH:
                return None
            return (position + START_OFFSETS[index]) % TRACK_LENGTH

        def capture_count(target: int) -> int:
            target_global = global_position(player_index, target)
            if target_global is None:
                return 0
            return sum(
                global_position(opponent_index, position) == target_global
                for opponent_index, opponent in opponents
                for position in state.get("pieces", {}).get(opponent.get("id"), [])
            )

        def capture_risk(target: int) -> int:
            """Count next-roll values that let an opponent capture this plane."""
            target_global = global_position(player_index, target)
            if target_global is None:
                return 0
            risky_rolls = set()
            for opponent_index, opponent in opponents:
                for position in state.get("pieces", {}).get(opponent.get("id"), []):
                    source_global = global_position(opponent_index, position)
                    if source_global is None:
                        continue
                    distance = (target_global - source_global) % TRACK_LENGTH
                    if 1 <= distance <= 6 and position + distance < TRACK_LENGTH:
                        risky_rolls.add(distance)
            return len(risky_rolls)

        def score(index: int) -> tuple[int, int, int, int, float]:
            source = positions[index]
            target = 0 if source == -1 else source + dice
            exact_finish = int(target == FINISH_POSITION)
            launch = int(source == -1)
            captures = capture_count(target)
            home_stretch = int(target >= TRACK_LENGTH)
            risk = capture_risk(target) if self.level == "strategy" else 0
            # Finish and captures are decisive. Strategy mode also prefers the
            # protected home stretch and avoids a square exposed to many rolls.
            tactical = exact_finish * 10_000 + captures * 1_200 + launch * 180
            tactical += home_stretch * 260 + target * 8 - risk * 150
            spread = -positions.count(source) if self.level == "strategy" else 0
            return exact_finish, captures, tactical, spread, random.random()

        return max(movable, key=score)


__all__ = ["FlightAI"]
