import pytest

from games.animal.board import DENS
from games.animal.engine import AnimalGame
from games.animal.piece import initial_pieces
from games.animal.rule import can_capture, legal_moves, validate_move
from games.core.engine import GameRuleError


def _piece(pieces, piece_id):
    return next(item for item in pieces if item["id"] == piece_id)


def test_animal_initial_board_and_rat_elephant_exception():
    pieces = initial_pieces()
    assert len(pieces) == 16
    assert len(legal_moves(pieces, "blue")) > 0
    blue_rat = _piece(pieces, "blue_rat")
    red_elephant = _piece(pieces, "red_elephant")
    red_rat = _piece(pieces, "red_rat")
    blue_elephant = _piece(pieces, "blue_elephant")
    blue_rat.update(x=2, y=6)
    assert can_capture(blue_rat, red_elephant)
    red_rat.update(x=5, y=2)
    assert not can_capture(blue_elephant, red_rat)


def test_animal_move_capture_den_and_turns():
    game = AnimalGame.create(["boy", "girl"])
    assert game.state["phase"] == "playing"
    game.move("boy", "blue_lion", 0, 1)
    assert game.state["turn_id"] == "girl"
    with pytest.raises(GameRuleError, match="回合"):
        game.move("boy", "blue_lion", 0, 2)

    game.state["turn_id"] = "boy"
    lion = _piece(game.state["pieces"], "blue_lion")
    lion.update(x=3, y=7)
    game.move("boy", "blue_lion", *DENS["red"])
    assert game.state["phase"] == "finished"
    assert game.state["winner_id"] == "boy"


def test_non_rat_cannot_enter_river():
    pieces = initial_pieces()
    wolf = _piece(pieces, "blue_wolf")
    wolf.update(x=1, y=2)
    with pytest.raises(GameRuleError, match="下水"):
        validate_move(pieces, wolf["id"], 1, 3, "blue")
