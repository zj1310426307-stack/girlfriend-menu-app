from collections import Counter

import pytest

from games.core.engine import GameRuleError
from games.landlord.card import build_deck
from games.landlord.engine import AI_ID, LandlordGame
from games.landlord.rule import beats, classify


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
