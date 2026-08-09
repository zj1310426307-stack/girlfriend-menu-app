"""V2.7 integration coverage for identities, archives, notifications and recovery."""
from datetime import date

from fastapi.testclient import TestClient

from test_api import admin_headers, app


def _headers(customer_id: str) -> dict:
    return {"X-Customer-Id": customer_id}


def test_unified_profile_timeline_anniversary_and_notification_ownership():
    owner = "gf_v27_profile"
    stranger = "gf_v27_stranger"
    with TestClient(app) as client:
        me = client.get("/api/users/me", headers=_headers(owner))
        assert me.status_code == 200
        assert me.json()["user_code"] == owner
        updated = client.put(
            "/api/users/me",
            headers=_headers(owner),
            json={"nickname": "我们", "avatar": "https://example.com/us.png"},
        )
        assert updated.status_code == 200
        assert updated.json()["nickname"] == "我们"

        memory = client.post(
            "/api/couple/memories",
            headers=_headers(owner),
            json={
                "type": "TRAVEL",
                "title": "第一次一起看海",
                "content": "把这一天留在时间轴。",
                "image_url": "",
                "event_date": date.today().isoformat(),
            },
        )
        assert memory.status_code == 201
        assert client.get("/api/couple/memories", headers=_headers(owner)).json()[0]["title"] == "第一次一起看海"
        assert client.delete(
            f"/api/couple/memories/{memory.json()['id']}", headers=_headers(stranger)
        ).status_code == 404

        anniversary = client.post(
            "/api/couple/dates",
            headers=_headers(owner),
            json={"title": "恋爱纪念日", "date": date.today().isoformat(), "repeat_type": "YEARLY", "reminder_days": 7},
        )
        assert anniversary.status_code == 201
        notifications = client.get("/api/notifications", headers=_headers(owner))
        assert notifications.status_code == 200
        reminder = next(item for item in notifications.json() if item["type"] == "ANNIVERSARY")
        assert client.patch(
            f"/api/notifications/{reminder['id']}/read", headers=_headers(stranger)
        ).status_code == 404
        assert client.patch(
            f"/api/notifications/{reminder['id']}/read", headers=_headers(owner)
        ).json()["is_read"] is True
        profile = client.get("/api/couple/profile", headers=_headers(owner)).json()
        assert profile["record_count"] >= 1
        assert profile["next_date_days"] == 0


def test_order_events_create_memories_notifications_and_dashboard():
    customer = "gf_v27_order"
    with TestClient(app) as client:
        admin = admin_headers(client)
        dish = client.get("/api/dishes").json()[0]
        order = client.post(
            "/api/orders",
            json={
                "items": [{"dish_id": dish["id"], "quantity": 1}],
                "note": "V2.7",
                "desired_time": "今晚",
                "customer_id": customer,
            },
        )
        assert order.status_code == 201
        for next_status in ("已接单", "制作中", "已完成"):
            completed = client.patch(
                f"/api/orders/{order.json()['id']}/status",
                headers=admin,
                json={"status": next_status},
            )
        assert completed.status_code == 200
        memories = client.get("/api/couple/memories", headers=_headers(customer)).json()
        assert {item["type"] for item in memories} >= {"FIRST_MEAL", "FIRST_COOK"}
        messages = client.get("/api/notifications", headers=_headers(customer)).json()
        assert any(item["type"] == "ORDER_STATUS" for item in messages)
        dashboard = client.get("/api/admin/dashboard", headers=admin)
        assert dashboard.status_code == 200
        assert {"today_orders", "today_games", "today_score", "redis"} <= set(dashboard.json())


def test_active_room_hashed_reconnect_and_generic_replay():
    player = "gf_v27_recovery"
    with TestClient(app) as client:
        room = client.post(
            "/api/games/flight/create",
            headers=_headers(player),
            json={"player_name": "我", "invite_code": "test-invite"},
        )
        assert room.status_code == 201
        code = room.json()["room_code"]
        issued = client.post(
            "/api/games/reconnect/token",
            headers=_headers(player),
            json={"room_code": code},
        )
        assert issued.status_code == 200
        assert len(issued.json()["reconnect_token"]) > 20
        active = client.get("/api/games/active", headers=_headers(player)).json()
        assert any(item["room_code"] == code for item in active)
        resumed = client.post(
            "/api/games/reconnect",
            json={"reconnect_token": issued.json()["reconnect_token"]},
        )
        assert resumed.status_code == 200
        assert resumed.json()["room_code"] == code
        assert client.post("/api/games/reconnect", json={"reconnect_token": "x" * 32}).status_code == 401

        chess = client.post(
            "/api/games/chess/create",
            headers=_headers(player),
            json={"player_name": "我", "mode": "ai", "difficulty": "rule", "invite_code": "test-invite"},
        ).json()
        finished = client.post(
            "/api/games/chess/move",
            headers=_headers(player),
            json={"room_code": chess["room_code"], "action": "RESIGN", "expected_version": chess["version"]},
        )
        assert finished.status_code == 200
        record = next(
            item for item in client.get("/api/games/records/my", headers=_headers(player)).json()
            if item["room_code"] == chess["room_code"]
        )
        replay = client.get(f"/api/games/records/{record['id']}/replay", headers=_headers(player))
        assert replay.status_code == 200
        assert replay.json()["game_type"] == "chinese_chess"
        assert client.get(
            f"/api/games/records/{record['id']}/replay", headers=_headers("gf_v27_outsider")
        ).status_code == 403
