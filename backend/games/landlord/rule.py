"""Supported V2.5 landlord hand classification and comparison rules."""
from __future__ import annotations

from collections import Counter
from itertools import combinations

from games.core.engine import GameRuleError


SUPPORTED_TYPES = {
    "single", "pair", "triple", "triple_single", "triple_pair", "straight",
    "pair_straight", "airplane", "airplane_single", "airplane_pair",
    "four_two_single", "four_two_pair", "bomb", "rocket",
}


def _is_consecutive(values: list[int], minimum: int) -> bool:
    return (
        len(values) >= minimum
        and values[-1] < 15
        and all(right - left == 1 for left, right in zip(values, values[1:]))
    )


def classify(cards: list[dict]) -> dict:
    """Classify a supported play and return its comparable main value."""
    if not cards:
        raise GameRuleError("至少选择一张牌")
    counts = Counter(card["value"] for card in cards)
    values = sorted(counts)
    total = len(cards)
    triple_values = sorted(value for value, count in counts.items() if count == 3)
    single_values = [value for value, count in counts.items() if count == 1]
    pair_values = [value for value, count in counts.items() if count == 2]
    if total == 1:
        kind, main = "single", values[0]
    elif total == 2 and values == [16, 17]:
        kind, main = "rocket", 17
    elif total == 2 and len(counts) == 1:
        kind, main = "pair", values[0]
    elif total == 3 and len(counts) == 1:
        kind, main = "triple", values[0]
    elif total == 4 and len(counts) == 1:
        kind, main = "bomb", values[0]
    elif total == 4 and sorted(counts.values()) == [1, 3]:
        kind, main = "triple_single", next(value for value, count in counts.items() if count == 3)
    elif total == 5 and sorted(counts.values()) == [2, 3]:
        kind, main = "triple_pair", next(value for value, count in counts.items() if count == 3)
    elif total >= 5 and len(counts) == total and _is_consecutive(values, 5):
        kind, main = "straight", values[-1]
    elif total >= 6 and total % 2 == 0 and all(count == 2 for count in counts.values()) and _is_consecutive(values, 3):
        kind, main = "pair_straight", values[-1]
    elif total >= 6 and total % 3 == 0 and all(count == 3 for count in counts.values()) and _is_consecutive(values, 2):
        kind, main = "airplane", values[-1]
    elif total == 6 and sorted(counts.values()) == [1, 1, 4]:
        kind, main = "four_two_single", next(value for value, count in counts.items() if count == 4)
    elif total == 8 and sorted(counts.values()) == [2, 2, 4]:
        kind, main = "four_two_pair", next(value for value, count in counts.items() if count == 4)
    elif (
        total >= 8 and total % 4 == 0 and len(triple_values) >= 2
        and len(single_values) == len(triple_values)
        and _is_consecutive(triple_values, 2)
    ):
        kind, main = "airplane_single", triple_values[-1]
    elif (
        total >= 10 and total % 5 == 0 and len(triple_values) >= 2
        and len(pair_values) == len(triple_values)
        and _is_consecutive(triple_values, 2)
    ):
        kind, main = "airplane_pair", triple_values[-1]
    else:
        raise GameRuleError("牌型不合法，请检查顺子、连对、飞机或四带二")
    return {"type": kind, "main": main, "length": total}


def beats(candidate: dict, previous: dict | None) -> bool:
    """Return whether one classified play legally beats the table play."""
    if previous is None:
        return True
    if candidate["type"] == "rocket":
        return previous["type"] != "rocket"
    if previous["type"] == "rocket":
        return False
    if candidate["type"] == "bomb" and previous["type"] != "bomb":
        return True
    if candidate["type"] != previous["type"] or candidate["length"] != previous["length"]:
        return False
    return candidate["main"] > previous["main"]


def _runs(values: list[int], minimum: int) -> list[list[int]]:
    """Enumerate every consecutive sub-run without including 2 or jokers."""
    allowed = sorted(value for value in values if value < 15)
    runs: list[list[int]] = []
    start = 0
    for index in range(1, len(allowed) + 1):
        if index < len(allowed) and allowed[index] == allowed[index - 1] + 1:
            continue
        block = allowed[start:index]
        for length in range(minimum, len(block) + 1):
            for offset in range(0, len(block) - length + 1):
                runs.append(block[offset:offset + length])
        start = index
    return runs


def enumerate_plays(hand: list[dict]) -> list[list[dict]]:
    """Generate supported legal combinations for hints and server AI.

    This deliberately builds combinations from rank groups instead of trying
    every hand subset, keeping worst-case work bounded for 20-card hands.
    """
    groups = {
        value: sorted(cards, key=lambda card: card["id"])
        for value in sorted({card["value"] for card in hand})
        if (cards := [card for card in hand if card["value"] == value])
    }
    plays: list[list[dict]] = []
    seen: set[tuple[str, ...]] = set()

    def add(cards: list[dict]) -> None:
        key = tuple(sorted(card["id"] for card in cards))
        if not key or key in seen:
            return
        try:
            classify(cards)
        except GameRuleError:
            return
        seen.add(key)
        plays.append(cards)

    for cards in groups.values():
        add(cards[:1])
        if len(cards) >= 2:
            add(cards[:2])
        if len(cards) >= 3:
            add(cards[:3])
        if len(cards) == 4:
            add(cards)
    if 16 in groups and 17 in groups:
        add([groups[16][0], groups[17][0]])

    triple_values = [value for value, cards in groups.items() if len(cards) >= 3]
    for triple_value in triple_values:
        for single_value, single_cards in groups.items():
            if single_value != triple_value:
                add(groups[triple_value][:3] + single_cards[:1])
                if len(single_cards) >= 2:
                    add(groups[triple_value][:3] + single_cards[:2])

    for run in _runs(list(groups), 5):
        add([groups[value][0] for value in run])
    pair_values = [value for value, cards in groups.items() if len(cards) >= 2]
    for run in _runs(pair_values, 3):
        add([card for value in run for card in groups[value][:2]])
    for run in _runs(triple_values, 2):
        triples = [card for value in run for card in groups[value][:3]]
        add(triples)
        wing_values = [value for value in groups if value not in run]
        for wings in combinations(wing_values, len(run)):
            add(triples + [groups[value][0] for value in wings])
        pair_wing_values = [value for value in wing_values if len(groups[value]) >= 2]
        for wings in combinations(pair_wing_values, len(run)):
            add(triples + [card for value in wings for card in groups[value][:2]])

    for bomb_value, bomb_cards in groups.items():
        if len(bomb_cards) != 4:
            continue
        other_values = [value for value in groups if value != bomb_value]
        for wings in combinations(other_values, 2):
            add(bomb_cards + [groups[value][0] for value in wings])
        pair_wings = [value for value in other_values if len(groups[value]) >= 2]
        for wings in combinations(pair_wings, 2):
            add(bomb_cards + [card for value in wings for card in groups[value][:2]])
    return plays


def suggest_play(hand: list[dict], previous: dict | None = None) -> list[dict] | None:
    """Return a conservative legal play, preserving bombs whenever possible."""
    legal = []
    for cards in enumerate_plays(hand):
        combo = classify(cards)
        if previous and not beats(combo, previous):
            continue
        bomb_cost = 2 if combo["type"] == "rocket" else 1 if combo["type"] == "bomb" else 0
        # Lead with efficient structures; follow with the smallest sufficient
        # main rank and keep high-value emergency cards for later.
        efficiency = -len(cards) if previous is None else len(cards)
        legal.append((bomb_cost, efficiency, combo["main"], cards))
    if not legal:
        return None
    return min(legal, key=lambda item: item[:3])[3]
