"""Consensual undo/draw coverage for the freestyle gomoku engine and room."""
import pytest

from gomoku import (
    BLACK,
    EMPTY,
    GameFinishedError,
    GomokuGame,
    NegotiationUnavailableError,
    OpponentMustAnswerError,
    UndoUnavailableError,
)


def new_game():
    return GomokuGame(["me", "girlfriend"])


def test_undo_removes_offerer_stone_and_restores_turn():
    game = new_game()
    game.move("me", 7, 7)
    game.move("girlfriend", 8, 8)
    assert game.turn_id == "me"

    game.offer_undo("me")
    assert game.negotiation == {"type": "undo", "by": "me"}
    assert game.answer_negotiation("girlfriend", "undo", True) is True

    # Reverting from the offerer's latest stone also drops the reply after it.
    assert game.negotiation is None
    assert game.board[7][7] == EMPTY
    assert game.board[8][8] == EMPTY
    assert game.move_count == 0
    assert game.turn_id == "me"
    assert game.last_move is None


def test_undo_only_own_stone_when_it_is_the_latest():
    game = new_game()
    game.move("me", 7, 7)
    game.move("girlfriend", 8, 8)
    assert game.turn_id == "me"

    # Girlfriend retracts her own stone while it is still the latest ply.
    game.offer_undo("girlfriend")
    game.answer_negotiation("me", "undo", True)

    assert game.board[7][7] == BLACK
    assert game.board[8][8] == EMPTY
    assert game.move_count == 1
    assert game.turn_id == "girlfriend"
    assert game.last_move["player_id"] == "me"


def test_undo_after_opponent_reply_rewinds_both_stones():
    game = new_game()
    game.move("me", 7, 7)
    game.move("girlfriend", 8, 8)
    game.move("me", 6, 6)
    assert game.turn_id == "girlfriend"

    game.offer_undo("girlfriend")
    game.answer_negotiation("me", "undo", True)

    assert game.board[8][8] == EMPTY
    assert game.board[6][6] == EMPTY
    assert game.board[7][7] == BLACK
    assert game.move_count == 1
    assert game.turn_id == "girlfriend"


def test_undo_requires_opponent_acceptance():
    game = new_game()
    game.move("me", 7, 7)
    game.offer_undo("me")

    with pytest.raises(OpponentMustAnswerError):
        game.answer_negotiation("me", "undo", True)

    # The offerer cancels their own request.
    assert game.answer_negotiation("me", "undo", False) is False
    assert game.negotiation is None
    assert game.move_count == 1


def test_declined_offer_keeps_board():
    game = new_game()
    game.move("me", 7, 7)
    game.offer_undo("me")
    assert game.answer_negotiation("girlfriend", "undo", False) is False
    assert game.board[7][7] == BLACK
    assert game.move_count == 1


def test_move_clears_pending_offer():
    game = new_game()
    game.move("me", 7, 7)
    game.offer_undo("me")
    game.move("girlfriend", 8, 8)

    assert game.negotiation is None
    with pytest.raises(NegotiationUnavailableError):
        game.answer_negotiation("me", "undo", True)


def test_undo_offer_without_stones_rejected():
    game = new_game()
    with pytest.raises(UndoUnavailableError):
        game.offer_undo("me")


def test_draw_agreement_finishes_round():
    game = new_game()
    game.move("me", 7, 7)
    game.offer_draw("girlfriend")
    assert game.answer_negotiation("me", "draw", True) is True

    assert game.phase == "finished"
    assert game.winner_id is None
    assert game.is_draw is True
    assert game.turn_id is None
    assert game.negotiation is None


def test_negotiation_rejected_after_game_finished():
    game = new_game()
    for index in range(5):
        game.move("me", index, 0)
        if index < 4:
            game.move("girlfriend", index, 14)
    assert game.phase == "finished"

    with pytest.raises(GameFinishedError):
        game.offer_draw("me")


def test_reset_clears_negotiation_and_history():
    game = new_game()
    game.move("me", 7, 7)
    game.offer_undo("me")
    snapshot = game.reset()

    assert snapshot["negotiation"] is None
    assert snapshot["move_count"] == 0
    assert snapshot["phase"] == "playing"
    assert snapshot["turn_id"] == "me"
