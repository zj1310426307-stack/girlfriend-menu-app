"""Canonical 54-card deck and JSON-safe card helpers."""
from __future__ import annotations


RANKS = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
SUITS = ("spade", "heart", "club", "diamond")
RANK_VALUE = {rank: index + 3 for index, rank in enumerate(RANKS)}
RANK_VALUE.update({"SJ": 16, "BJ": 17})


def build_deck() -> list[dict]:
    """Return all 54 unique cards; callers shuffle a fresh copy server-side."""
    cards = [
        {
            "id": f"{rank}-{suit}",
            "rank": rank,
            "suit": suit,
            "value": RANK_VALUE[rank],
            "color": "red" if suit in {"heart", "diamond"} else "black",
        }
        for rank in RANKS
        for suit in SUITS
    ]
    cards.extend(
        (
            {"id": "SJ-joker", "rank": "SJ", "suit": "joker", "value": 16, "color": "black"},
            {"id": "BJ-joker", "rank": "BJ", "suit": "joker", "value": 17, "color": "red"},
        )
    )
    return cards


def sort_cards(cards: list[dict]) -> list[dict]:
    """Sort low-to-high by rank and stable card id for predictable UI."""
    return sorted(cards, key=lambda card: (card["value"], card["id"]))
