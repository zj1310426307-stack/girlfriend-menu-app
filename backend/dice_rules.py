"""Pure, deterministic Liar's Dice rules used by the real-time transport."""

from __future__ import annotations


def is_higher_bid(current_bid: dict | None, next_bid: dict | None) -> bool:
    if not next_bid:
        return False
    quantity = int(next_bid.get("quantity") or 0)
    face = int(next_bid.get("face") or 0)
    if quantity < 1 or face < 1 or face > 6:
        return False
    if not current_bid:
        return True
    return quantity > int(current_bid["quantity"]) or (
        quantity == int(current_bid["quantity"]) and face > int(current_bid["face"])
    )


def count_matching_dice(all_values: list[int], face: int, ones_are_wild: bool = True) -> int:
    if face < 1 or face > 6:
        raise ValueError("face must be between 1 and 6")
    return sum(value == face or (ones_are_wild and face != 1 and value == 1) for value in all_values)


def resolve_challenge(all_values: list[int], bid: dict, challenger_id: str) -> dict:
    actual_count = count_matching_dice(all_values, int(bid["face"]))
    succeeded = actual_count >= int(bid["quantity"])
    bidder_id = str(bid["bidder_id"])
    return {
        "actual_count": actual_count,
        "bid_succeeded": succeeded,
        "winner_id": bidder_id if succeeded else challenger_id,
        "loser_id": challenger_id if succeeded else bidder_id,
    }
