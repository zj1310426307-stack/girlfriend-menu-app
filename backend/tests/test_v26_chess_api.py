"""Integration coverage for V2.6 chess, replay, ranking and AI companion APIs."""
from fastapi.testclient import TestClient

from test_api import app
import models
from database import SessionLocal


def _headers(customer_id: str) -> dict:
    """Build the minimal device-identity header used by game APIs."""
    return {"X-Customer-Id": customer_id}


def test_chess_ai_room_move_replay_and_server_owned_state():
    player = "gf_v26_ai_player"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/chess/create",
            headers=_headers(player),
            json={"player_name": "我", "mode": "ai", "difficulty": "rule", "invite_code": "test-invite"},
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload["game_type"] == "chinese_chess"
        assert payload["state"]["my_color"] == "red"
        assert len(payload["state"]["pieces"]) == 32
        moved = client.post(
            "/api/games/chess/move",
            headers=_headers(player),
            json={"room_code": payload["room_code"], "action": "MOVE", "from_pos": "a7", "to_pos": "a6", "expected_version": payload["version"]},
        )
        assert moved.status_code == 200
        state = moved.json()
        assert state["version"] == payload["version"] + 1
        assert state["state"]["turn_id"] == player
        assert state["state"]["move_count"] == 2
        game_id = state["state"]["chess_game_id"]
        history = client.get(f"/api/games/chess/{game_id}/history", headers=_headers(player))
        assert history.status_code == 200
        assert len(history.json()["moves"]) == 2
        assert client.get(f"/api/games/chess/{game_id}/history", headers=_headers("stranger")).status_code == 403
        assert client.get(f"/api/games/chess/{payload['room_code']}/state", headers=_headers("stranger")).status_code == 403


def test_chess_couple_join_finish_rewards_statistics_memories_and_achievements():
    red, black = "gf_v26_red", "gf_v26_black"
    with TestClient(app) as client:
        waiting = client.post(
            "/api/games/chess/create",
            headers=_headers(red),
            json={"player_name": "他", "mode": "couple", "difficulty": "rule", "invite_code": "test-invite"},
        ).json()
        assert waiting["state"]["phase"] == "waiting"
        joined = client.post(
            "/api/games/chess/join",
            headers=_headers(black),
            json={"room_code": waiting["room_code"], "player_name": "她", "invite_code": "test-invite"},
        )
        assert joined.status_code == 200
        assert joined.json()["state"]["my_color"] == "black"
        finished = client.post(
            "/api/games/chess/move",
            headers=_headers(red),
            json={"room_code": waiting["room_code"], "action": "RESIGN", "expected_version": joined.json()["version"]},
        )
        assert finished.status_code == 200
        assert finished.json()["state"]["winner_id"] == black
        records = client.get("/api/games/records/my", headers=_headers(black)).json()
        assert any(item["game_type"] == "chinese_chess" and item["winner"] == black for item in records)
        memories = client.get("/api/games/memories/my", headers=_headers(black))
        assert memories.status_code == 200
        assert {item["event"] for item in memories.json()} >= {"FIRST_CHESS", "CHESS_RESULT"}
        ranking = client.get("/api/games/ranking", headers=_headers(black))
        assert ranking.status_code == 200
        chess_stat = next(item for item in ranking.json()["my_statistics"] if item["game_type"] == "chinese_chess")
        assert chess_stat["wins"] >= 1
        assert all("player_id" not in item for item in ranking.json()["monthly_ranking"])
        achievements = client.get("/api/games/achievements", headers=_headers(black)).json()
        assert any(item["code"] == "chess_first" and item["unlocked"] for item in achievements)


def test_ai_catalog_daily_summary_and_admin_chess_stat():
    player = "gf_v26_summary"
    with TestClient(app) as client:
        personas = client.get("/api/games/ai/players")
        assert personas.status_code == 200
        assert any(item["game_type"] == "chinese_chess" and item["level"] == "rule" for item in personas.json())
        summary = client.get("/api/games/ai/summary", headers=_headers(player))
        assert summary.status_code == 200
        assert {"meals", "games", "love_score_change", "message", "recommendation"} <= set(summary.json())

        login = client.post("/api/admin/login", json={"password": "test-password", "invite_code": "test-invite"})
        stats = client.get("/api/admin/games/stats", headers={"Authorization": f"Bearer {login.json()['token']}"})
        assert stats.status_code == 200
        assert "chess_games" in stats.json()

    with SessionLocal() as db:
        assert db.query(models.AIPlayer).count() >= 8
