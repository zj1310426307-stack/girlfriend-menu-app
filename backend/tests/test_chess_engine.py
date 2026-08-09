"""Rule coverage for the pure V2.6 Chinese-chess engine."""
from copy import deepcopy
import random

import pytest

from games.chess.ai import ChessAI
from games.chess.engine import AI_ID, ChessGame
from games.chess.piece import initial_pieces
from games.chess.rule import in_check, legal_moves, validate_move
from games.core.engine import GameRuleError


def _only(*pieces):
    """Return a compact live test position."""
    return [dict(piece, alive=True) for piece in pieces]


def _p(piece_id, color, kind, x, y, label="子"):
    """Build a test piece matching the engine contract."""
    return {"id": piece_id, "color": color, "kind": kind, "x": x, "y": y, "label": label}


def test_initial_board_and_piece_specific_blocking_rules():
    pieces = initial_pieces()
    assert len(pieces) == 32
    assert len({piece["id"] for piece in pieces}) == 32
    with pytest.raises(GameRuleError, match="不能这样走"):
        validate_move(pieces, "red_rook_0", 0, 5, "red")
    with pytest.raises(GameRuleError, match="不能这样走"):
        validate_move(pieces, "red_horse_0", 3, 8, "red")
    horse = _only(
        _p("red_king", "red", "king", 4, 9, "帅"),
        _p("black_king", "black", "king", 3, 0, "将"),
        _p("horse", "red", "horse", 4, 5, "马"),
        _p("leg", "red", "pawn", 5, 5, "兵"),
    )
    with pytest.raises(GameRuleError):
        validate_move(horse, "horse", 6, 6, "red")


def test_elephant_palace_pawn_and_cannon_rules():
    base = _only(
        _p("red_king", "red", "king", 4, 9, "帅"),
        _p("black_king", "black", "king", 3, 0, "将"),
        _p("elephant", "red", "elephant", 2, 5, "相"),
        _p("guard", "red", "guard", 3, 9, "仕"),
        _p("pawn", "red", "pawn", 4, 6, "兵"),
    )
    with pytest.raises(GameRuleError):
        validate_move(base, "elephant", 4, 3, "red")
    with pytest.raises(GameRuleError):
        validate_move(base, "guard", 2, 8, "red")
    with pytest.raises(GameRuleError):
        validate_move(base, "pawn", 5, 6, "red")
    crossed = deepcopy(base)
    next(piece for piece in crossed if piece["id"] == "pawn")["y"] = 4
    assert validate_move(crossed, "pawn", 5, 4, "red")

    cannon = _only(
        _p("red_king", "red", "king", 4, 9, "帅"),
        _p("black_king", "black", "king", 3, 0, "将"),
        _p("cannon", "red", "cannon", 0, 5, "炮"),
        _p("screen", "red", "pawn", 0, 3, "兵"),
        _p("target", "black", "rook", 0, 0, "车"),
    )
    assert validate_move(cannon, "cannon", 0, 0, "red")["target"]["id"] == "target"
    with pytest.raises(GameRuleError):
        validate_move(cannon, "cannon", 0, 2, "red")


def test_flying_generals_self_check_and_check_detection():
    pieces = _only(
        _p("red_king", "red", "king", 4, 9, "帅"),
        _p("black_king", "black", "king", 4, 0, "将"),
        _p("blocker", "red", "rook", 4, 5, "车"),
    )
    with pytest.raises(GameRuleError, match="将帅"):
        validate_move(pieces, "blocker", 5, 5, "red")
    checking = _only(
        _p("red_king", "red", "king", 4, 9, "帅"),
        _p("black_king", "black", "king", 4, 0, "将"),
        _p("red_rook", "red", "rook", 4, 1, "车"),
    )
    assert in_check(checking, "black")


def test_turn_history_resign_and_defensive_serialization():
    game = ChessGame.create(["boy", "girl"], {"boy": "我", "girl": "她"})
    moved = game.move("boy", "red_pawn_0", 0, 5)
    assert moved["turn_id"] == "girl"
    assert moved["move_history"][0]["notation"].endswith("a7→a6")
    with pytest.raises(GameRuleError, match="不是你的回合"):
        game.move("boy", "red_pawn_1", 2, 5)
    snapshot = game.serialize()
    snapshot["pieces"].clear()
    assert len(game.serialize()["pieces"]) == 32
    finished = game.apply("girl", "RESIGN")
    assert finished["winner_id"] == "boy"


def test_checkmate_no_moves_finishes_and_ai_prioritizes_capture():
    game = ChessGame.create(["boy", AI_ID], difficulty="rule")
    state = game.serialize()
    state["pieces"] = _only(
        _p("red_king", "red", "king", 4, 9, "帅"),
        _p("black_king", "black", "king", 4, 0, "将"),
        _p("block", "black", "guard", 4, 5, "士"),
        _p("red_rook", "red", "rook", 0, 1, "车"),
        _p("black_rook", "black", "rook", 0, 3, "车"),
    )
    state["turn_id"] = "boy"
    game = ChessGame(state)
    result = game.move("boy", "red_rook", 0, 3)
    assert result["last_move"]["captured"] == "black_rook"

    ai = ChessAI("rule", random.Random(1))
    state["turn_id"] = AI_ID
    state["colors"] = {"boy": "red", AI_ID: "black"}
    decision = ai.choose_action(state, AI_ID)
    assert decision["action"] == "MOVE"
    assert any(move["piece_id"] == decision["piece_id"] for move in legal_moves(state["pieces"], "black"))


def test_long_check_third_consecutive_check_is_rejected():
    game = ChessGame.create(["boy", "girl"])
    state = game.serialize()
    state["pieces"] = _only(
        _p("red_king", "red", "king", 4, 9, "帅"),
        _p("black_king", "black", "king", 4, 0, "将"),
        _p("screen", "black", "guard", 4, 4, "士"),
        _p("red_rook", "red", "rook", 3, 1, "车"),
    )
    state["turn_id"] = "boy"
    state["consecutive_checks"] = {"boy": 2}
    game = ChessGame(state)
    with pytest.raises(GameRuleError, match="长将"):
        game.move("boy", "red_rook", 4, 1)
