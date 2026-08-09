"""Secure server-side shuffle and 17/17/17 + 3 card dealing."""
from __future__ import annotations

import random

from .card import build_deck, sort_cards


def deal(rng: random.Random | random.SystemRandom | None = None) -> tuple[list[list[dict]], list[dict]]:
    """Shuffle a complete deck and return three hands plus bottom cards."""
    source = rng or random.SystemRandom()
    deck = build_deck()
    source.shuffle(deck)
    hands = [sort_cards(deck[index * 17 : (index + 1) * 17]) for index in range(3)]
    return hands, sort_cards(deck[51:])
