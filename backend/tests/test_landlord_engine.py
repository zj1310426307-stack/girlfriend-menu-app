from collections import Counter

import pytest

from games.core.engine import GameRuleError
from games.landlord.card import build_deck
from games.landlord.engine import AI_ID, LandlordGame
from games.landlord.rule import beats, classify, enumerate_plays, suggest_play


def _cards(*values):
    deck = build_deck()
    result = []
    used = set()
    for value in values:
        card = next(card for card in deck if card["value"] == value and card["id"] not in used)
        used.add(card["id"])
        result.append(card)
    return result


def test_complete_deck_and_supported_combinations():
    deck = build_deck()
    assert len(deck) == 54
    assert len({card["id"] for card in deck}) == 54
    assert Counter(card["rank"] for card in deck)["3"] == 4
    assert classify(_cards(3))["type"] == "single"
    assert classify(_cards(4, 4))["type"] == "pair"
    assert classify(_cards(5, 5, 5, 8))["type"] == "triple_single"
    assert classify(_cards(3, 4, 5, 6, 7))["type"] == "straight"
    assert classify(_cards(9, 9, 9, 9))["type"] == "bomb"
    rocket = classify(_cards(16, 17))
    assert rocket["type"] == "rocket"
    assert beats(rocket, classify(_cards(12, 12, 12, 12)))
    with pytest.raises(GameRuleError):
        classify(_cards(3, 3, 4))


def test_extended_combinations_and_server_hint():
    pair_straight = classify(_cards(3, 3, 4, 4, 5, 5))
    triple_pair = classify(_cards(5, 5, 5, 8, 8))
    airplane = classify(_cards(6, 6, 6, 7, 7, 7))
    airplane_wings = classify(_cards(6, 6, 6, 7, 7, 7, 9, 10))
    airplane_pairs = classify(_cards(6, 6, 6, 7, 7, 7, 9, 9, 10, 10))
    four_two = classify(_cards(8, 8, 8, 8, 11, 12))
    assert pair_straight["type"] == "pair_straight"
    assert triple_pair["type"] == "triple_pair"
    assert airplane["type"] == "airplane"
    assert airplane_wings["type"] == "airplane_single"
    assert airplane_pairs["type"] == "airplane_pair"
    assert four_two["type"] == "four_two_single"
    hand = _cards(3, 3, 4, 4, 5, 5, 15, 16, 17)
    plays = enumerate_plays(hand)
    assert any(classify(play)["type"] == "pair_straight" for play in plays)
    hint = suggest_play(hand, classify(_cards(10)))
    assert hint and beats(classify(hint), classify(_cards(10)))


def test_landlord_deals_bids_hides_hands_and_finishes():
    game = LandlordGame.waiting(["boy", "girl"], {"boy": "我", "girl": "她"})
    assert game.state["phase"] == "bidding"
    assert sorted(len(hand) for hand in game.state["hands"].values()) == [17, 17, 17]
    assert len(game.state["bottom_cards"]) == 3
    assert game.public_state("boy")["my_hand"]
    assert "hands" not in game.public_state("boy")

    game.bid("boy", True)
    game.bid("girl", False)
    game.bid(AI_ID, False)
    assert game.state["phase"] == "playing"
    assert game.state["landlord_id"] == "boy"
    assert len(game.state["hands"]["boy"]) == 20
    view = game.public_state("boy")
    assert "suggested_card_ids" in view

    final_card = game.state["hands"]["boy"][0]
    game.state["hands"]["boy"] = [final_card]
    game.state["turn_id"] = "boy"
    game.state["last_play"] = None
    game.play("boy", [final_card["id"]])
    assert game.state["phase"] == "finished"
    assert game.state["winner_id"] == "boy"


def test_landlord_rejects_out_of_turn_and_illegal_pass():
    game = LandlordGame.waiting(["boy", "girl"])
    with pytest.raises(GameRuleError, match="叫地主"):
        game.bid("girl", True)
    game.bid("boy", True)
    game.bid("girl", False)
    game.bid(AI_ID, False)
    with pytest.raises(GameRuleError, match="不能不出"):
        game.pass_turn("boy")
