from copy import deepcopy
from unittest.mock import patch

from fastapi.testclient import TestClient

import models
from database import SessionLocal
from test_api import admin_headers, app


def _headers(customer_id):
    return {"X-Customer-Id": customer_id}


def test_daily_tasks_manual_and_authoritative_completion():
    customer_id = "gf_daily_tasks"
    with TestClient(app) as client:
        today = client.get("/api/couple/tasks/today", headers=_headers(customer_id))
        assert today.status_code == 200
        payload = today.json()
        assert payload["total_count"] == 4
        assert payload["completed_count"] == 0
        compliment = next(task for task in payload["tasks"] if task["type"] == "COMPLIMENT")
        meal = next(task for task in payload["tasks"] if task["type"] == "MEAL")

        automatic_rejected = client.post(
            f"/api/couple/tasks/{meal['id']}/complete", headers=_headers(customer_id)
        )
        assert automatic_rejected.status_code == 409

        completed = client.post(
            f"/api/couple/tasks/{compliment['id']}/complete", headers=_headers(customer_id)
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert client.post(
            f"/api/couple/tasks/{compliment['id']}/complete", headers=_headers(customer_id)
        ).status_code == 200
        summary = client.get("/api/couple/tasks/today", headers=_headers(customer_id)).json()
        assert summary["completed_count"] == 1
        assert summary["earned_score"] == 2
        score = client.get("/api/couple/score", headers=_headers(customer_id)).json()
        assert score["points_total"] == 2


def test_flight_room_server_dice_event_finish_and_persistence():
    first_id = "gf_flight_boy"
    second_id = "gf_flight_girl"
    with TestClient(app) as client:
        assert client.post(
            "/api/games/flight/create",
            headers=_headers(first_id),
            json={"player_name": "男朋友", "invite_code": "wrong"},
        ).status_code == 401
        created = client.post(
            "/api/games/flight/create",
            headers=_headers(first_id),
            json={"player_name": "男朋友", "invite_code": "test-invite"},
        )
        assert created.status_code == 201
        room_code = created.json()["room_code"]
        assert created.json()["state"]["phase"] == "waiting"

        joined = client.post(
            "/api/games/flight/join",
            headers=_headers(second_id),
            json={
                "room_code": room_code,
                "player_name": "女朋友",
                "invite_code": "test-invite",
            },
        )
        assert joined.status_code == 200
        assert joined.json()["state"]["phase"] == "playing"
        assert client.get(
            f"/api/games/flight/{room_code}/state",
            headers=_headers("gf_stranger"),
        ).status_code == 403

        with SessionLocal() as db:
            room = db.query(models.GameRoom).filter(models.GameRoom.room_code == room_code).one()
            row = db.query(models.GameState).filter(models.GameState.room_id == room.id).one()
            state = deepcopy(row.state)
            state["turn_id"] = first_id
            state["pieces"][first_id] = [3, -1, -1, -1]
            state["dice"] = None
            state["movable"] = []
            row.state = state
            db.commit()

        with patch("flight_service.secrets.randbelow", return_value=0):
            rolled = client.post(
                "/api/games/flight/action",
                headers=_headers(first_id),
                json={"room_code": room_code, "action": "ROLL_DICE"},
            )
        assert rolled.status_code == 200
        assert rolled.json()["state"]["dice"] == 1
        moved = client.post(
            "/api/games/flight/action",
            headers=_headers(first_id),
            json={"room_code": room_code, "action": "MOVE_PIECE", "piece_index": 0},
        )
        assert moved.status_code == 200
        event = moved.json()["state"]["pending_event"]
        assert event["type"] == "LOVE"
        assert event["content"]
        assert event["score"] == 3
        completed = client.post(
            "/api/games/flight/action",
            headers=_headers(first_id),
            json={"room_code": room_code, "action": "COMPLETE_EVENT"},
        )
        assert completed.status_code == 200
        assert completed.json()["state"]["pending_event"] is None

        with SessionLocal() as db:
            room = db.query(models.GameRoom).filter(models.GameRoom.room_code == room_code).one()
            row = db.query(models.GameState).filter(models.GameState.room_id == room.id).one()
            state = deepcopy(row.state)
            state.update({"turn_id": first_id, "dice": None, "movable": [], "pending_event": None})
            state["pieces"][first_id] = [32, 32, 32, 31]
            row.state = state
            db.commit()

        with patch("flight_service.secrets.randbelow", return_value=0):
            assert client.post(
                "/api/games/flight/action",
                headers=_headers(first_id),
                json={"room_code": room_code, "action": "ROLL_DICE"},
            ).status_code == 200
        finished = client.post(
            "/api/games/flight/action",
            headers=_headers(first_id),
            json={"room_code": room_code, "action": "MOVE_PIECE", "piece_index": 3},
        )
        assert finished.status_code == 200
        assert finished.json()["state"]["winner_id"] == first_id

        records = client.get("/api/games/records/my", headers=_headers(first_id)).json()
        flight_records = [record for record in records if record["room_code"] == room_code]
        assert len(flight_records) == 1
        assert flight_records[0]["game_type"] == "aeroplane"
        interactions = client.get("/api/couple/tasks/today", headers=_headers(first_id)).json()
        assert interactions["recent_interactions"][0]["status"] == "completed"
        assert interactions["completed_count"] >= 1

        stats = client.get("/api/admin/games/stats", headers=admin_headers(client))
        assert stats.status_code == 200
        assert stats.json()["flight_games"] >= 1
        assert stats.json()["interaction_count"] >= 1
        assert len(stats.json()["love_score_growth"]) == 7
