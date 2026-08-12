import time

from fastapi.testclient import TestClient

import crud
import models
from database import SessionLocal
from api.routes.websocket import _persist_completed_game
from test_api import admin_headers, app


def _join(player_id, name):
    return {
        "type": "join",
        "game": "gomoku",
        "data": {
            "player_id": player_id,
            "name": name,
            "invite_code": "test-invite",
        },
    }


def _move(socket, x, y):
    socket.send_json({
        "type": "MOVE",
        "game": "gomoku",
        "data": {"x": x, "y": y},
    })


def _receive_pair(first, second):
    first_state = first.receive_json()
    second_state = second.receive_json()
    assert first_state["type"] == second_state["type"] == "state"
    assert first_state["game"] == second_state["game"] == "gomoku"
    return first_state["data"], second_state["data"]


def test_gomoku_online_round_records_scores_and_rematch():
    first_id = "gf_gomoku_black"
    second_id = "gf_gomoku_white"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/rooms",
            json={
                "game_type": "gomoku",
                "creator": first_id,
                "invite_code": "test-invite",
            },
        )
        assert created.status_code == 201
        room_code = created.json()["room_code"]
        assert created.json()["players"] == []

        with client.websocket_connect(f"/ws/game/{room_code}") as first:
            first.send_json(_join(first_id, "我"))
            waiting = first.receive_json()["data"]
            assert waiting["phase"] == "waiting"
            assert waiting["players"][0]["color"] == "black"

            with client.websocket_connect(f"/ws/game/{room_code}") as second:
                second.send_json(_join(second_id, "女朋友"))
                first_ready, second_ready = _receive_pair(first, second)
                assert first_ready["phase"] == second_ready["phase"] == "playing"
                assert first_ready["turn_id"] == first_id
                assert [player["color"] for player in first_ready["players"]] == [
                    "black",
                    "white",
                ]

                with client.websocket_connect(f"/ws/game/{room_code}") as third:
                    third.send_json(_join("gf_gomoku_third", "第三位玩家"))
                    room_full = third.receive_json()
                    assert room_full["type"] == "error"
                    assert "满" in room_full["message"]

                # White cannot move before black; the server owns turn validation.
                _move(second, 12, 12)
                rejected = second.receive_json()
                assert rejected["type"] == "error"
                assert "轮到" in rejected["message"]

                black_moves = [(3, 7), (4, 7), (5, 7), (6, 7), (7, 7)]
                white_moves = [(0, 0), (0, 1), (0, 2), (0, 3)]
                for index, black_move in enumerate(black_moves):
                    _move(first, *black_move)
                    first_state, second_state = _receive_pair(first, second)
                    if index < len(white_moves):
                        assert first_state["phase"] == "playing"
                        _move(second, *white_moves[index])
                        _receive_pair(first, second)

                assert first_state["phase"] == second_state["phase"] == "finished"
                assert first_state["winner_id"] == first_id
                assert first_state["outcome"]["reward"]
                assert first_state["move_count"] == 9

                records = []
                for _ in range(20):
                    response = client.get(
                        "/api/games/records/my",
                        headers={"X-Customer-Id": first_id},
                    )
                    assert response.status_code == 200
                    records = response.json()
                    if records:
                        break
                    time.sleep(0.02)
                assert len(records) == 1
                assert records[0]["room_code"] == room_code
                assert records[0]["winner"] == first_id
                assert records[0]["result"]["move_count"] == 9
                assert len(records[0]["players"]) == 2

                winner_score = client.get(
                    "/api/couple/score",
                    headers={"X-Customer-Id": first_id},
                ).json()
                loser_score = client.get(
                    "/api/couple/score",
                    headers={"X-Customer-Id": second_id},
                ).json()
                assert winner_score["points_total"] == 9
                assert loser_score["points_total"] == 4
                assert winner_score["month_games"] == 1

                first.send_json({"type": "REMATCH", "game": "gomoku", "data": {}})
                first_vote, second_vote = _receive_pair(first, second)
                assert first_vote["phase"] == "finished"
                assert any(player["rematch_ready"] for player in second_vote["players"])
                second.send_json({"type": "rematch", "game": "gomoku", "data": {}})
                first_rematch, second_rematch = _receive_pair(first, second)
                assert first_rematch["phase"] == second_rematch["phase"] == "playing"
                assert first_rematch["round"] == 2
                assert first_rematch["move_count"] == 0

        stats = client.get(
            "/api/admin/games/stats",
            headers=admin_headers(client),
        )
        assert stats.status_code == 200
        assert stats.json()["gomoku_games"] >= 1
        assert stats.json()["most_played_game"]
        assert stats.json()["love_score_change"] >= 7


def test_three_consecutive_wins_award_once_and_settlement_is_idempotent():
    winner_id = "gf_gomoku_streak_winner"
    opponent_id = "gf_gomoku_streak_opponent"

    with TestClient(app):
        with SessionLocal() as db:
            room = crud.create_game_room(db, "gomoku", winner_id)
            crud.join_game_room(db, room.room_code, winner_id)
            crud.join_game_room(db, room.room_code, opponent_id)
            room_code = room.room_code

        for round_number in range(1, 4):
            event = {
                "room_code": room_code,
                "game_type": "gomoku",
                "round_number": round_number,
                "players": [winner_id, opponent_id],
                "winner_id": winner_id,
                "duration": 30,
                "result": {"winner_id": winner_id, "move_count": 9},
            }
            _persist_completed_game(event)
            _persist_completed_game(event)

        with SessionLocal() as db:
            winner_points = sum(
                entry.score
                for entry in db.query(models.LoveScore)
                .filter(models.LoveScore.customer_id == winner_id)
                .all()
            )
            opponent_points = sum(
                entry.score
                for entry in db.query(models.LoveScore)
                .filter(models.LoveScore.customer_id == opponent_id)
                .all()
            )
            streak_awards = (
                db.query(models.LoveScore)
                .filter(
                    models.LoveScore.customer_id == winner_id,
                    models.LoveScore.type == "SPECIAL_EVENT",
                    models.LoveScore.description == "五子棋三连胜",
                )
                .count()
            )
            game_score_change = crud.game_stats(db)["love_score_change"]

        assert winner_points == 31
        assert opponent_points == 6
        assert streak_awards == 1
        assert game_score_change >= winner_points + opponent_points
