from fastapi.testclient import TestClient
from copy import deepcopy
import secrets

from test_api import admin_headers, app
import achievement_service
import models
from database import SessionLocal
from games.landlord.card import build_deck


def _headers(customer_id):
    return {"X-Customer-Id": customer_id}


def test_landlord_room_private_state_actions_and_version_conflict():
    boy, girl = "gf_landlord_boy", "gf_landlord_girl"
    with TestClient(app) as client:
        denied = client.post(
            "/api/games/landlord/create",
            headers=_headers(boy),
            json={"player_name": "我", "difficulty": "rule", "invite_code": "bad"},
        )
        assert denied.status_code == 401
        created = client.post(
            "/api/games/landlord/create",
            headers=_headers(boy),
            json={"player_name": "我", "difficulty": "rule", "invite_code": "test-invite"},
        )
        assert created.status_code == 201
        room_code = created.json()["room_code"]
        joined = client.post(
            "/api/games/landlord/join",
            headers=_headers(girl),
            json={"room_code": room_code, "player_name": "她", "invite_code": "test-invite"},
        )
        assert joined.status_code == 200
        payload = joined.json()
        assert payload["state"]["phase"] == "bidding"
        assert len(payload["state"]["my_hand"]) == 17
        assert "hands" not in payload["state"]
        version = payload["version"]

        first_bid = client.post(
            "/api/games/landlord/action",
            headers=_headers(boy),
            json={"room_code": room_code, "action": "BID", "bid": True, "expected_version": version},
        )
        assert first_bid.status_code == 200
        assert first_bid.json()["version"] == version + 1
        stale = client.post(
            "/api/games/landlord/action",
            headers=_headers(boy),
            json={"room_code": room_code, "action": "CHAT", "text": "加油", "expected_version": version},
        )
        assert stale.status_code == 409
        state = client.get(f"/api/games/{room_code}/state", headers=_headers(girl))
        assert state.status_code == 200
        assert state.json()["version"] == version + 1
        assert client.get(f"/api/games/{room_code}/state", headers=_headers("stranger")).status_code == 403


def test_animal_ai_and_couple_rooms_use_authoritative_versions():
    solo = "gf_animal_solo"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/animal/create",
            headers=_headers(solo),
            json={
                "player_name": "我",
                "mode": "ai",
                "difficulty": "rule",
                "invite_code": "test-invite",
            },
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload["state"]["phase"] == "playing"
        assert payload["state"]["my_color"] == "blue"
        moved = client.post(
            "/api/games/animal/move",
            headers=_headers(solo),
            json={
                "room_code": payload["room_code"],
                "action": "MOVE",
                "piece_id": "blue_lion",
                "x": 0,
                "y": 1,
                "expected_version": payload["version"],
            },
        )
        assert moved.status_code == 200
        assert moved.json()["version"] == payload["version"] + 1
        assert moved.json()["state"]["turn_id"] == solo

        first, second = "gf_animal_first", "gf_animal_second"
        waiting = client.post(
            "/api/games/animal/create",
            headers=_headers(first),
            json={"player_name": "我", "mode": "couple", "invite_code": "test-invite"},
        ).json()
        assert waiting["state"]["phase"] == "waiting"
        joined = client.post(
            "/api/games/animal/join",
            headers=_headers(second),
            json={"room_code": waiting["room_code"], "player_name": "她", "invite_code": "test-invite"},
        )
        assert joined.status_code == 200
        assert joined.json()["state"]["phase"] == "playing"


def test_achievement_unlock_is_idempotent_and_admin_stats_expand():
    customer_id = "gf_v25_achievement"
    with TestClient(app) as client:
        with SessionLocal() as db:
            room = models.GameRoom(
                room_code=f"A{secrets.token_hex(3).upper()}"[:6],
                game_type="jungle",
                creator=customer_id,
                status="finished",
                max_players=2,
            )
            db.add(room)
            db.flush()
            db.add(models.GamePlayer(room_id=room.id, player_id=customer_id, seat=1))
            db.add(
                models.GameRecord(
                    room_id=room.id,
                    round_number=1,
                    game_type="jungle",
                    winner=customer_id,
                    duration=10,
                    result={"_settlement": "complete"},
                )
            )
            db.commit()
            achievement_service.evaluate_achievements(db, customer_id)
            achievement_service.evaluate_achievements(db, customer_id)
            assert db.query(models.UserAchievement).filter(
                models.UserAchievement.customer_id == customer_id
            ).count() >= 2
            counts = [
                row[0]
                for row in db.query(models.UserAchievement.achievement_id)
                .filter(models.UserAchievement.customer_id == customer_id)
                .all()
            ]
            assert len(counts) == len(set(counts))

        achievements = client.get("/api/games/achievements", headers=_headers(customer_id))
        assert achievements.status_code == 200
        assert any(item["unlocked"] for item in achievements.json())
        stats = client.get("/api/admin/games/stats", headers=admin_headers(client))
        assert stats.status_code == 200
        assert {"landlord_games", "animal_games", "today_games", "ai_games", "popular_games", "achievement_unlocks"} <= set(stats.json())


def test_landlord_finish_settles_record_rewards_achievement_and_love_task():
    boy, girl = "gf_landlord_finish_boy", "gf_landlord_finish_girl"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/landlord/create",
            headers=_headers(boy),
            json={"player_name": "我", "difficulty": "rule", "invite_code": "test-invite"},
        ).json()
        joined = client.post(
            "/api/games/landlord/join",
            headers=_headers(girl),
            json={"room_code": created["room_code"], "player_name": "她", "invite_code": "test-invite"},
        ).json()
        with SessionLocal() as db:
            room = db.query(models.GameRoom).filter(models.GameRoom.room_code == created["room_code"]).one()
            session = db.query(models.GameSession).filter(models.GameSession.room_id == room.id).one()
            state = deepcopy(session.state)
            deck = build_deck()
            state.update(
                phase="playing",
                turn_id=boy,
                landlord_id=boy,
                last_play=None,
                pass_count=0,
            )
            state["hands"] = {boy: [deck[0]], girl: [deck[1]], "ai_landlord": [deck[2]]}
            session.state = state
            db.commit()
            version = session.version
            card_id = deck[0]["id"]

        finished = client.post(
            "/api/games/landlord/action",
            headers=_headers(boy),
            json={
                "room_code": created["room_code"],
                "action": "PLAY",
                "card_ids": [card_id],
                "expected_version": version,
            },
        )
        assert finished.status_code == 200
        assert finished.json()["state"]["winner_id"] == boy
        records = client.get("/api/games/records/my", headers=_headers(boy)).json()
        assert any(record["room_code"] == created["room_code"] for record in records)
        tasks = client.get("/api/games/tasks/my", headers=_headers(boy)).json()
        assert tasks and tasks[0]["status"] == "pending"
        completed = client.post(f"/api/games/tasks/{tasks[0]['id']}/complete", headers=_headers(boy))
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        types = {entry["type"] for entry in client.get("/api/couple/score/history", headers=_headers(boy)).json()}
        assert {"GAME_PLAY", "GAME_WIN", "GAME_BONUS", "ACHIEVEMENT", "LOVE_TASK"} <= types


def test_animal_ai_finish_writes_record_and_bonus():
    player_id = "gf_animal_finish"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/animal/create",
            headers=_headers(player_id),
            json={"player_name": "我", "mode": "ai", "difficulty": "rule", "invite_code": "test-invite"},
        ).json()
        with SessionLocal() as db:
            room = db.query(models.GameRoom).filter(models.GameRoom.room_code == created["room_code"]).one()
            session = db.query(models.GameSession).filter(models.GameSession.room_id == room.id).one()
            state = deepcopy(session.state)
            lion = next(piece for piece in state["pieces"] if piece["id"] == "blue_lion")
            lion.update(x=3, y=7)
            state["turn_id"] = player_id
            session.state = state
            db.commit()
            version = session.version

        finished = client.post(
            "/api/games/animal/move",
            headers=_headers(player_id),
            json={
                "room_code": created["room_code"],
                "action": "MOVE",
                "piece_id": "blue_lion",
                "x": 3,
                "y": 8,
                "expected_version": version,
            },
        )
        assert finished.status_code == 200
        assert finished.json()["state"]["winner_id"] == player_id
        records = client.get("/api/games/records/my", headers=_headers(player_id)).json()
        assert any(record["room_code"] == created["room_code"] for record in records)
        history = client.get("/api/couple/score/history", headers=_headers(player_id)).json()
        assert any(entry["type"] == "GAME_BONUS" for entry in history)
