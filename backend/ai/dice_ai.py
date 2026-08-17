"""Probability-based Liar's Dice AI for the unified local strategy registry."""

from __future__ import annotations

from collections import Counter
from math import comb
import random

from ai.base import AIPlayer
from dice_rules import is_higher_bid


DICE_PER_PLAYER = 5


class DiceAI(AIPlayer):
    """Choose a legal bid or challenge using only observable and private dice."""

    @staticmethod
    def _support(dice: list[int], face: int) -> int:
        return sum(value == face or (face != 1 and value == 1) for value in dice)

    @classmethod
    def estimate_bid_probability(
        cls,
        quantity: int,
        face: int,
        own_dice: list[int],
        player_count: int,
    ) -> float:
        """Estimate bid truth under the existing wild-one rule."""
        needed = quantity - cls._support(own_dice, face)
        unknown = max(0, player_count * DICE_PER_PLAYER - len(own_dice))
        if needed <= 0:
            return 1.0
        if needed > unknown:
            return 0.0
        probability = 1 / 6 if face == 1 else 1 / 3
        return min(
            1.0,
            sum(
                comb(unknown, hits)
                * probability**hits
                * (1 - probability) ** (unknown - hits)
                for hits in range(needed, unknown + 1)
            ),
        )

    @classmethod
    def _legal_bids(cls, current: dict | None, max_quantity: int) -> list[dict]:
        return [
            {"quantity": quantity, "face": face}
            for quantity in range(1, max_quantity + 1)
            for face in range(1, 7)
            if is_higher_bid(current, {"quantity": quantity, "face": face})
        ]

    def choose_action(self, state: dict, player_id: str) -> dict:
        """Return the shared uppercase server action envelope."""
        players = state.get("players") or []
        player_count = max(2, int(state.get("player_count") or len(players) or 2))
        own_dice = list(
            state.get("own_dice")
            or (state.get("dice") or {}).get(player_id)
            or []
        )
        if not own_dice:
            raise ValueError("骰子 AI 缺少自己的骰子")
        current = state.get("current_bid")
        max_quantity = player_count * DICE_PER_PLAYER
        legal = self._legal_bids(current, max_quantity)

        if self.level == "random":
            if current and random.random() < 0.35:
                return {"action": "CHALLENGE"}
            selected = random.choice(legal) if legal else None
        else:
            truth = (
                self.estimate_bid_probability(
                    int(current["quantity"]),
                    int(current["face"]),
                    own_dice,
                    player_count,
                )
                if current
                else 1.0
            )
            threshold = 0.38 if self.level == "strategy" else 0.28
            history = [
                item
                for item in (state.get("opponent_history") or [])
                if "bid_succeeded" in item
            ]
            if self.level == "strategy" and history:
                bluff_rate = sum(not item["bid_succeeded"] for item in history) / len(history)
                threshold = min(0.55, max(0.28, threshold + (bluff_rate - 0.5) * 0.2))
            if current and truth < threshold:
                return {"action": "CHALLENGE"}
            support = Counter(own_dice)
            selected = max(
                legal,
                key=lambda bid: (
                    self.estimate_bid_probability(
                        bid["quantity"],
                        bid["face"],
                        own_dice,
                        player_count,
                    ),
                    support[bid["face"]] + (support[1] if bid["face"] != 1 else 0),
                    -bid["quantity"],
                    -bid["face"],
                ),
                default=None,
            )
        if selected is None:
            return {"action": "CHALLENGE"}
        return {"action": "BID", **selected}


__all__ = ["DiceAI"]
