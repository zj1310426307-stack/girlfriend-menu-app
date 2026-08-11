"""Tactical regression tests for the 2.9.2 game-quality pass."""

from ai.flight_ai import FlightAI
from games.animal.ai import AnimalAI
from games.chess.ai import ChessAI


def test_flight_strategy_prefers_an_immediate_capture():
    state = {
        "players": [{"id": "human"}, {"id": "ai"}],
        "pieces": {"human": [22, -1, -1, -1], "ai": [5, 14, -1, -1]},
        "movable": [0, 1],
        "dice": 3,
    }
    assert FlightAI("strategy").choose_piece(state, "ai") == 0


def test_animal_strategy_enters_the_open_opponent_den():
    state = {
        "colors": {"ai": "blue", "human": "red"},
        "pieces": [
            {"id": "blue_cat", "color": "blue", "kind": "cat", "rank": 2, "x": 3, "y": 7, "alive": True},
            {"id": "red_cat", "color": "red", "kind": "cat", "rank": 2, "x": 0, "y": 6, "alive": True},
        ],
    }
    action = AnimalAI("strategy").choose_action(state, "ai")
    assert (action["x"], action["y"]) == (3, 8)


def test_chess_strategy_takes_an_exposed_king():
    pieces = [
        {"id": "black_king", "color": "black", "kind": "king", "label": "将", "x": 3, "y": 0, "alive": True},
        {"id": "black_rook", "color": "black", "kind": "rook", "label": "车", "x": 4, "y": 8, "alive": True},
        {"id": "red_king", "color": "red", "kind": "king", "label": "帅", "x": 4, "y": 9, "alive": True},
    ]
    action = ChessAI("strategy").choose_action(
        {"colors": {"ai": "black"}, "pieces": pieces},
        "ai",
    )
    assert action["piece_id"] == "black_rook"
    assert (action["x"], action["y"]) == (4, 9)
