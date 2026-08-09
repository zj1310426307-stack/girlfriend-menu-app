import pytest

from flight import FlightGame, InvalidPiece, NotYourTurn, initial_state


PLAYERS = [
    {"id": "boy", "name": "男朋友", "seat": 1},
    {"id": "girl", "name": "女朋友", "seat": 2},
]


def test_waiting_state_starts_after_second_player_and_requires_six_to_take_off():
    game = FlightGame(initial_state(PLAYERS[:1]))
    assert game.state["phase"] == "waiting"
    game.sync_players(PLAYERS)
    assert game.state["phase"] == "playing"
    assert game.state["turn_id"] == "boy"

    state = game.roll_dice("boy", 3)
    assert state["last_action"]["passed"] is True
    assert state["turn_id"] == "girl"
    with pytest.raises(NotYourTurn):
        game.roll_dice("boy", 6)

    game.roll_dice("girl", 6)
    game.move_piece("girl", 0)
    assert game.state["pieces"]["girl"][0] == 0
    assert game.state["turn_id"] == "girl"


def test_capture_event_square_and_exact_finish():
    state = initial_state(PLAYERS)
    state["pieces"]["boy"] = [3, 32, 32, 32]
    game = FlightGame(state)
    game.roll_dice("boy", 1)
    game.move_piece("boy", 0)
    assert game.state["pending_event"]["type"] == "LOVE"
    game.attach_event({"log_id": 7, "content": "夸夸对方", "score": 3})
    game.complete_event("boy")
    assert game.state["turn_id"] == "girl"

    game.state["turn_id"] = "boy"
    game.state["pieces"]["boy"][0] = 31
    game.roll_dice("boy", 2)
    assert game.state["last_action"]["passed"] is True
    assert game.state["pieces"]["boy"][0] == 31

    game.state["turn_id"] = "boy"
    game.roll_dice("boy", 1)
    finished = game.move_piece("boy", 0)
    assert finished["phase"] == "finished"
    assert finished["winner_id"] == "boy"


def test_takeoff_captures_opponent_on_shared_track_and_rejects_wrong_piece():
    state = initial_state(PLAYERS)
    state["pieces"]["girl"][0] = 14
    game = FlightGame(state)
    game.roll_dice("boy", 6)
    with pytest.raises(InvalidPiece):
        game.move_piece("boy", 4)
    result = game.move_piece("boy", 0)
    assert result["pieces"]["girl"][0] == -1
    assert result["last_action"]["captured"] == [{"player_id": "girl", "piece_index": 0}]
