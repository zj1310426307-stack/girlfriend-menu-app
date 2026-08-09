import pytest

from dice_rules import count_matching_dice, is_higher_bid, resolve_challenge


def test_bid_order_and_boundaries():
    assert is_higher_bid(None, {"quantity": 1, "face": 1})
    assert is_higher_bid({"quantity": 3, "face": 4}, {"quantity": 3, "face": 5})
    assert is_higher_bid({"quantity": 3, "face": 6}, {"quantity": 4, "face": 1})
    assert not is_higher_bid({"quantity": 3, "face": 4}, {"quantity": 3, "face": 4})
    assert not is_higher_bid(None, {"quantity": 0, "face": 6})
    assert not is_higher_bid(None, {"quantity": 2, "face": 7})


def test_wild_ones_and_open_cup_counting():
    values = [1, 2, 2, 3, 6, 1, 5, 5, 4, 2]
    assert count_matching_dice(values, 2) == 5
    assert count_matching_dice(values, 1) == 2
    assert count_matching_dice(values, 2, ones_are_wild=False) == 3
    result = resolve_challenge(values, {"quantity": 6, "face": 2, "bidder_id": "a"}, "b")
    assert result == {
        "actual_count": 5,
        "bid_succeeded": False,
        "winner_id": "b",
        "loser_id": "a",
    }


def test_invalid_face_is_rejected():
    with pytest.raises(ValueError):
        count_matching_dice([1, 2], 0)
