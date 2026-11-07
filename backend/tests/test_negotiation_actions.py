"""Consensual undo/draw negotiation coverage for chess and animal engines."""
import pytest

from games.animal.engine import AnimalGame
from games.chess.engine import ChessGame
from games.core.engine import GameRuleError


def _piece(pieces, piece_id):
    return next(item for item in pieces if item["id"] == piece_id)


def _chess_couple_game():
    return ChessGame.create(["boy", "girl"])


def _animal_couple_game():
    return AnimalGame.create(["boy", "girl"])


def test_chess_undo_reverts_offerer_move_and_reply():
    game = _chess_couple_game()
    game.move("boy", "red_pawn_0", 0, 5)
    game.move("girl", "black_pawn_0", 0, 4)
    assert game.state["move_count"] == 2

    game.apply("boy", "UNDO_OFFER")
    assert game.state["negotiation"] == {"type": "undo", "by": "boy"}
    game.apply("girl", "UNDO_ACCEPT")

    assert game.state["negotiation"] is None
    assert game.state["move_count"] == 0
    assert game.state["move_history"] == []
    assert game.state["turn_id"] == "boy"
    assert _piece(game.state["pieces"], "red_pawn_0")["y"] == 6
    assert _piece(game.state["pieces"], "black_pawn_0")["y"] == 3
    assert game.state["phase"] == "playing"


def test_chess_undo_revives_captured_piece():
    game = _chess_couple_game()
    # Two pawns meet on file 0, the red pawn captures forward.
    game.move("boy", "red_pawn_0", 0, 5)
    game.move("girl", "black_pawn_0", 0, 4)
    game.move("boy", "red_pawn_0", 0, 4)
    assert _piece(game.state["pieces"], "black_pawn_0")["alive"] is False

    game.apply("boy", "UNDO_OFFER")
    game.apply("girl", "UNDO_ACCEPT")

    assert _piece(game.state["pieces"], "black_pawn_0")["alive"] is True
    assert _piece(game.state["pieces"], "black_pawn_0")["y"] == 4
    assert _piece(game.state["pieces"], "red_pawn_0")["y"] == 5
    assert game.state["turn_id"] == "boy"


def test_chess_undo_requires_opponent_acceptance():
    game = _chess_couple_game()
    game.move("boy", "red_pawn_0", 0, 5)
    game.apply("boy", "UNDO_OFFER")
    with pytest.raises(GameRuleError, match="只能由对方回应"):
        game.apply("boy", "UNDO_ACCEPT")
    game.apply("girl", "UNDO_DECLINE")
    assert game.state["negotiation"] is None
    assert game.state["move_count"] == 1


def test_chess_move_clears_pending_negotiation():
    game = _chess_couple_game()
    game.move("boy", "red_pawn_0", 0, 5)
    game.apply("boy", "UNDO_OFFER")
    game.move("girl", "black_pawn_0", 0, 4)
    assert game.state["negotiation"] is None
    with pytest.raises(GameRuleError, match="没有待回应"):
        game.apply("boy", "UNDO_ACCEPT")


def test_chess_undo_offer_without_moves_rejected():
    game = _chess_couple_game()
    with pytest.raises(GameRuleError, match="可以悔"):
        game.apply("boy", "UNDO_OFFER")


def test_chess_draw_agreement_finishes_without_winner():
    game = _chess_couple_game()
    game.move("boy", "red_pawn_0", 0, 5)
    game.apply("girl", "DRAW_OFFER")
    game.apply("boy", "DRAW_ACCEPT")
    assert game.state["phase"] == "finished"
    assert game.state["winner_id"] is None
    assert game.state["draw_reason"] == "agreement"
    assert game.state["result_reason"] == "draw"


def test_chess_negotiation_blocked_in_ai_mode():
    game = ChessGame.create(["boy", "ai_chess"])
    game.state["mode"] = "ai"
    with pytest.raises(GameRuleError, match="人机模式"):
        game.apply("boy", "UNDO_OFFER")
    with pytest.raises(GameRuleError, match="人机模式"):
        game.apply("boy", "DRAW_OFFER")


def test_animal_undo_reverts_own_last_ply():
    game = _animal_couple_game()
    game.move("boy", "blue_lion", 0, 1)
    assert game.state["turn_id"] == "girl"

    game.apply("boy", "UNDO_OFFER")
    assert game.state["negotiation"] == {"type": "undo", "by": "boy"}
    game.apply("girl", "UNDO_ACCEPT")

    assert _piece(game.state["pieces"], "blue_lion")["y"] == 0
    assert game.state["turn_id"] == "boy"
    assert game.state["move_count"] == 0
    assert game.state["last_move"] is None


def test_animal_undo_blocked_after_opponent_reply():
    game = _animal_couple_game()
    game.move("boy", "blue_lion", 0, 1)
    game.move("girl", "red_lion", 6, 7)
    with pytest.raises(GameRuleError, match="只能悔自己最近一步"):
        game.apply("boy", "UNDO_OFFER")


def test_animal_draw_agreement():
    game = _animal_couple_game()
    game.move("boy", "blue_lion", 0, 1)
    game.apply("boy", "DRAW_OFFER")
    game.apply("girl", "DRAW_ACCEPT")
    assert game.state["phase"] == "finished"
    assert game.state["winner_id"] is None
    assert game.state["draw_reason"] == "agreement"
