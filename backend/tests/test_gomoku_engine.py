import json

import pytest

from gomoku import (
    BLACK,
    BOARD_SIZE,
    WHITE,
    GameFinishedError,
    GameFullError,
    GameNotReadyError,
    GomokuGame,
    NotYourTurnError,
    OccupiedCellError,
    OutOfBoundsError,
    PlayerAlreadyJoinedError,
    UnknownPlayerError,
)


def new_game():
    return GomokuGame(["me", "girlfriend"])


@pytest.mark.parametrize(
    ("black_moves", "white_moves"),
    [
        ([(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)], [(10, 14), (11, 14), (12, 14), (13, 14)]),
        ([(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)], [(14, 10), (14, 11), (14, 12), (14, 13)]),
        ([(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)], [(14, 10), (14, 11), (14, 12), (14, 13)]),
        ([(14, 0), (13, 1), (12, 2), (11, 3), (10, 4)], [(0, 10), (0, 11), (0, 12), (0, 13)]),
    ],
    ids=["horizontal", "vertical", "down_diagonal", "up_diagonal"],
)
def test_black_wins_in_all_four_directions(black_moves, white_moves):
    game = new_game()

    for index, (x, y) in enumerate(black_moves):
        result = game.move("me", x, y)
        if index < len(white_moves):
            game.move("girlfriend", *white_moves[index])

    assert result["phase"] == "finished"
    assert result["winner_id"] == "me"
    assert result["turn_id"] is None
    assert game.serialize()["winner_color"] == "black"


def test_player_assignment_waiting_state_and_turn_order():
    game = GomokuGame()
    assert game.phase == "waiting"
    assert game.add_player("me") == "black"
    assert game.phase == "waiting"

    with pytest.raises(GameNotReadyError) as exc_info:
        game.move("me", 7, 7)
    assert exc_info.value.code == "GAME_NOT_READY"

    assert game.add_player("girlfriend") == "white"
    assert game.phase == "playing"
    assert game.turn_id == "me"

    with pytest.raises(NotYourTurnError):
        game.move("girlfriend", 7, 7)

    game.move("me", 7, 7)
    assert game.turn_id == "girlfriend"
    game.move("girlfriend", 8, 7)
    assert game.turn_id == "me"


def test_join_and_move_validation_errors_are_precise():
    game = new_game()

    with pytest.raises(PlayerAlreadyJoinedError):
        game.add_player("me")
    with pytest.raises(GameFullError):
        game.add_player("third")
    with pytest.raises(UnknownPlayerError):
        game.move("stranger", 0, 0)
    with pytest.raises(OutOfBoundsError) as exc_info:
        game.move("me", -1, BOARD_SIZE)
    assert exc_info.value.serialize()["details"] == {
        "x": -1,
        "y": BOARD_SIZE,
        "size": BOARD_SIZE,
    }

    game.move("me", 0, 0)
    game.move("girlfriend", 1, 0)
    with pytest.raises(OccupiedCellError):
        game.move("me", 0, 0)


def test_full_board_without_five_is_a_draw():
    game = new_game()

    # This four-cell periodic coloring has no run of five horizontally,
    # vertically, or diagonally, and contains 113 black / 112 white cells.
    black_cells = []
    white_cells = []
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            target = BLACK if (x + 2 * y) % 4 < 2 else WHITE
            (black_cells if target == BLACK else white_cells).append((x, y))

    assert len(black_cells) == 113
    assert len(white_cells) == 112
    for index, black_cell in enumerate(black_cells):
        result = game.move("me", *black_cell)
        if index < len(white_cells):
            game.move("girlfriend", *white_cells[index])

    assert result["phase"] == "finished"
    assert result["is_draw"] is True
    assert result["winner_id"] is None
    assert game.move_count == BOARD_SIZE * BOARD_SIZE


def test_finished_game_rejects_moves_and_reset_starts_next_round():
    game = new_game()
    for x in range(5):
        game.move("me", x, 0)
        if x < 4:
            game.move("girlfriend", x, 1)

    with pytest.raises(GameFinishedError):
        game.move("girlfriend", 10, 10)

    snapshot = game.reset()
    assert snapshot["phase"] == "playing"
    assert snapshot["round"] == 2
    assert snapshot["turn_id"] == "me"
    assert snapshot["winner_id"] is None
    assert snapshot["last_move"] is None
    assert snapshot["move_count"] == 0
    assert all(cell == 0 for row in snapshot["board"] for cell in row)


def test_serialized_state_is_json_safe_and_cannot_mutate_game_board():
    game = new_game()
    game.move("me", 7, 7)
    snapshot = game.serialize()

    assert json.loads(json.dumps(snapshot, ensure_ascii=False))["last_move"] == {
        "player_id": "me",
        "color": "black",
        "x": 7,
        "y": 7,
    }
    snapshot["board"][7][7] = 0
    assert game.board[7][7] == BLACK
