"""Supported V2.5 landlord hand classification and comparison rules."""
from __future__ import annotations

from collections import Counter

from games.core.engine import GameRuleError


SUPPORTED_TYPES = {"single", "pair", "triple", "triple_single", "straight", "bomb", "rocket"}


def classify(cards: list[dict]) -> dict:
    """Classify a supported play and return its comparable main value."""
    if not cards:
        raise GameRuleError("至少选择一张牌")
    counts = Counter(card["value"] for card in cards)
    values = sorted(counts)
    total = len(cards)
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
    elif (
        total >= 5
        and len(counts) == total
        and values[-1] < 15
        and all(right - left == 1 for left, right in zip(values, values[1:]))
    ):
        kind, main = "straight", values[-1]
    else:
        raise GameRuleError("当前版本支持单张、对子、三张、三带一、顺子、炸弹和王炸")
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
