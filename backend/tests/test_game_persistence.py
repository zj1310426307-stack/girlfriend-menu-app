from fastapi.testclient import TestClient

from test_api import app

import crud
import schemas
from database import SessionLocal


def test_game_players_round_records_and_stats_are_persistent_and_idempotent():
    first_id = "gf_persistence_first"
    second_id = "gf_persistence_second"

    with TestClient(app):
        with SessionLocal() as db:
            room = crud.create_game_room(db, "gomoku", first_id)
            assert room.players == []

            first = crud.join_game_room(db, room.room_code, first_id)
            assert first.seat == 1
            assert crud.join_game_room(db, room.room_code, first_id).id == first.id

            second = crud.join_game_room(db, room.room_code, second_id)
            assert second.seat == 2
            assert crud.get_game_room(db, room.room_code).status == "playing"

            first_round = crud.finish_game_room(
                db,
                room.room_code,
                first_id,
                42,
                {"move_count": 9},
                1,
            )
            retried = crud.finish_game_room(
                db,
                room.room_code,
                first_id,
                999,
                {"move_count": 99},
                1,
            )
            assert retried.id == first_round.id
            assert retried.duration == 42

            crud.update_game_room_status(db, room.room_code, "playing")
            second_round = crud.finish_game_room(
                db,
                room.room_code,
                second_id,
                60,
                {"move_count": 12},
                2,
            )
            assert second_round.id != first_round.id

            history = crud.list_game_records(db, second_id)
            assert [record.round_number for record in history] == [2, 1]
            payload = schemas.GameRecordOut.model_validate(history[0])
            assert payload.room_code == room.room_code
            assert [player.seat for player in payload.players] == [1, 2]

            stats = schemas.GameStatsOut.model_validate(crud.game_stats(db))
            assert stats.total_games >= 2
            assert stats.gomoku_games >= 2
            # Other integration tests may already have persisted a completed
            # dice round; the aggregate should include it instead of pinning a
            # global most-played value to this isolated room.
            assert stats.dice_games >= 1
            assert stats.most_played_game

    # A fresh database session must still see both rounds.
    with SessionLocal() as db:
        persisted = crud.list_game_records(db, first_id)
        assert [record.round_number for record in persisted] == [2, 1]
