"""Simple random/rule landlord AI used as the third player."""
from __future__ import annotations

from collections import Counter
import random

from ai.base import AIPlayer

from .rule import beats, classify


class LandlordAI(AIPlayer):
    """Choose a legal conservative move without reading hidden human hands."""

    def should_bid(self, hand: list[dict]) -> bool:
        """Bid with enough high cards, bombs or a rocket; random AI is looser."""
        values = Counter(card["value"] for card in hand)
        strength = sum(card["value"] >= 14 for card in hand) + 2 * sum(count == 4 for count in values.values())
        if {16, 17}.issubset(values):
            strength += 3
        return random.choice((True, False)) if self.level == "random" else strength >= 5

    def choose_action(self, state: dict, player_id: str) -> dict:
        """Return BID, PLAY or PASS for the AI's current phase."""
        if state["phase"] == "bidding":
            return {"action": "BID", "bid": self.should_bid(state["hands"][player_id])}
        hand = sorted(state["hands"][player_id], key=lambda card: (card["value"], card["id"]))
        previous = state.get("last_play")
        if not previous or previous.get("player_id") == player_id:
            return {"action": "PLAY", "card_ids": [hand[0]["id"]]}
        previous_combo = previous["combo"]
        candidates: list[list[dict]] = [[card] for card in hand]
        grouped = Counter(card["value"] for card in hand)
        for value, count in grouped.items():
            same = [card for card in hand if card["value"] == value]
            if count >= 2:
                candidates.append(same[:2])
            if count >= 3:
                candidates.append(same[:3])
            if count == 4:
                candidates.append(same)
        jokers = [card for card in hand if card["value"] in {16, 17}]
        if len(jokers) == 2:
            candidates.append(jokers)
        legal = []
        for cards in candidates:
            try:
                combo = classify(cards)
            except ValueError:
                continue
            if beats(combo, previous_combo):
                legal.append((combo["type"] in {"bomb", "rocket"}, combo["main"], cards))
        if not legal:
            return {"action": "PASS"}
        _, _, cards = sorted(legal, key=lambda item: (item[0], item[1], len(item[2])))[0]
        return {"action": "PLAY", "card_ids": [card["id"] for card in cards]}
