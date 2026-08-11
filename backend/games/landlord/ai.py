"""Simple random/rule landlord AI used as the third player."""
from __future__ import annotations

from collections import Counter
import random

from ai.base import AIPlayer

from .rule import beats, classify, enumerate_plays, suggest_play


class LandlordAI(AIPlayer):
    """Choose a legal conservative move without reading hidden human hands."""

    def should_bid(self, hand: list[dict]) -> bool:
        """Bid with enough high cards, bombs or a rocket; random AI is looser."""
        values = Counter(card["value"] for card in hand)
        strength = sum(card["value"] >= 14 for card in hand) + 2 * sum(count == 4 for count in values.values())
        if {16, 17}.issubset(values):
            strength += 3
        threshold = 6 if self.level == "strategy" else 5
        return random.choice((True, False)) if self.level == "random" else strength >= threshold

    def choose_action(self, state: dict, player_id: str) -> dict:
        """Return BID, PLAY or PASS for the AI's current phase."""
        if state["phase"] == "bidding":
            return {"action": "BID", "bid": self.should_bid(state["hands"][player_id])}
        hand = sorted(state["hands"][player_id], key=lambda card: (card["value"], card["id"]))
        previous = state.get("last_play")
        previous_combo = None if not previous or previous.get("player_id") == player_id else previous["combo"]
        if self.level == "random":
            legal = [
                cards for cards in enumerate_plays(hand)
                if previous_combo is None or beats(classify(cards), previous_combo)
            ]
            cards = random.choice(legal) if legal else None
        else:
            cards = suggest_play(hand, previous_combo)
            if self.level == "strategy" and previous_combo is None:
                # Strategy mode prefers shedding the largest non-bomb pattern.
                non_bombs = [
                    play for play in enumerate_plays(hand)
                    if classify(play)["type"] not in {"bomb", "rocket"}
                ]
                if non_bombs:
                    cards = max(
                        non_bombs,
                        key=lambda play: (len(play), -classify(play)["main"]),
                    )
        if not cards:
            return {"action": "PASS"}
        return {"action": "PLAY", "card_ids": [card["id"] for card in cards]}
