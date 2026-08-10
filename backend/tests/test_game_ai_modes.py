"""Regression coverage for the unified human-versus-AI game modes."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.gomoku_ai import GomokuAI
from test_api import app


def _headers(customer_id: str) -> dict[str, str]:
    return {"X-Customer-Id": customer_id}


def test_gomoku_ai_finishes_an_immediate_five():
    board = [[0 for _ in range(15)] for _ in range(15)]
    board[7][3:7] = [2, 2, 2, 2]
    action = GomokuAI("strategy").choose_action(
        {
            "board": board,
            "players": [
                {"id": "human", "color": "black"},
                {"id": "ai_gomoku", "color": "white"},
            ],
        },
        "ai_gomoku",
    )
    assert action["action"] == "MOVE"
    assert action["y"] == 7
    assert action["x"] in {2, 7}


def test_gomoku_ai_room_moves_over_the_authoritative_websocket():
    player_id = "gf_gomoku_ai_mode"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/rooms",
            json={
                "game_type": "gomoku",
                "creator": player_id,
                "mode": "ai",
                "difficulty": "rule",
                "invite_code": "test-invite",
            },
        )
        assert created.status_code == 201
        room_code = created.json()["room_code"]
        assert len(created.json()["players"]) == 2

        with client.websocket_connect(f"/ws/game/{room_code}") as socket:
            socket.send_json({
                "type": "join",
                "game": "gomoku",
                "data": {
                    "player_id": player_id,
                    "name": "我",
                    "invite_code": "test-invite",
                },
            })
            state = socket.receive_json()["data"]
            assert state["mode"] == "ai"
            assert state["phase"] == "playing"
            assert state["turn_id"] == player_id

            socket.send_json({"type": "move", "game": "gomoku", "data": {"x": 7, "y": 7}})
            human_state = socket.receive_json()["data"]
            ai_state = socket.receive_json()["data"]
            assert human_state["move_count"] == 1
            assert ai_state["move_count"] == 2
            assert ai_state["last_move"]["player_id"] == "ai_gomoku"
            assert ai_state["turn_id"] == player_id


def test_flight_ai_room_and_landlord_solo_table_start_immediately():
    flight_player = "gf_flight_ai_mode"
    landlord_player = "gf_landlord_ai_mode"
    with TestClient(app) as client:
        flight = client.post(
            "/api/games/flight/create",
            headers=_headers(flight_player),
            json={
                "player_name": "我",
                "mode": "ai",
                "difficulty": "rule",
                "invite_code": "test-invite",
            },
        )
        assert flight.status_code == 201
        flight_payload = flight.json()
        assert flight_payload["state"]["phase"] == "playing"
        assert flight_payload["state"]["mode"] == "ai"
        assert len(flight_payload["state"]["players"]) == 2
        with patch("flight_service.secrets.randbelow", return_value=0):
            rolled = client.post(
                "/api/games/flight/action",
                headers=_headers(flight_player),
                json={"room_code": flight_payload["room_code"], "action": "ROLL_DICE"},
            )
        assert rolled.status_code == 200
        assert rolled.json()["state"]["turn_id"] == flight_player
        assert rolled.json()["state"]["ai_turn_summary"][-1]["dice"] == 1

        landlord = client.post(
            "/api/games/landlord/create",
            headers=_headers(landlord_player),
            json={
                "player_name": "我",
                "mode": "ai",
                "difficulty": "rule",
                "invite_code": "test-invite",
            },
        )
        assert landlord.status_code == 201
        landlord_state = landlord.json()["state"]
        assert landlord_state["phase"] == "bidding"
        assert landlord_state["mode"] == "ai"
        assert len(landlord_state["players"]) == 3
        assert sum(player.startswith("ai_") for player in landlord_state["players"]) == 2
        assert len(landlord_state["my_hand"]) == 17
        assert "hands" not in landlord_state
