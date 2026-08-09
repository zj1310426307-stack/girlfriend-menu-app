import os
from pathlib import Path


TEST_DB = Path(__file__).with_name("test_girlfriend_menu.db")
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["ADMIN_INVITE_CODE"] = "test-invite"
os.environ["ADMIN_SECRET"] = "test-secret-with-enough-entropy"

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402

from database import engine  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database():
    yield
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


def admin_headers(client: TestClient):
    response = client.post(
        "/api/admin/login",
        json={"password": "test-password", "invite_code": "test-invite"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def admin_token(client: TestClient):
    return admin_headers(client)["Authorization"].removeprefix("Bearer ")


def test_health_and_database_readiness():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        ready = client.get("/api/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] == "sqlite"


def test_order_review_and_safe_dish_removal():
    with TestClient(app) as client:
        headers = admin_headers(client)
        created_dish = client.post(
            "/api/dishes",
            headers=headers,
            json={
                "name": "CI 测试菜",
                "description": "只存在于自动测试数据库",
                "category": "测试",
                "price": 12.5,
                "image_url": "",
            },
        )
        assert created_dish.status_code == 201
        dish_id = created_dish.json()["id"]

        created_order = client.post(
            "/api/orders",
            json={
                "items": [{"dish_id": dish_id, "quantity": 2}],
                "note": "少盐",
                "desired_time": "今晚七点",
                "customer_id": "gf_ci_test",
            },
        )
        assert created_order.status_code == 201
        order_id = created_order.json()["id"]

        too_early = client.post(
            f"/api/orders/{order_id}/review",
            json={"rating": 5, "want_again": "想吃", "comment": ""},
        )
        assert too_early.status_code == 400

        completed = client.patch(
            f"/api/orders/{order_id}/status",
            headers=headers,
            json={"status": "已完成"},
        )
        assert completed.status_code == 200
        reviewed = client.post(
            f"/api/orders/{order_id}/review",
            json={"rating": 5, "want_again": "想吃", "comment": "很好吃"},
        )
        assert reviewed.status_code == 201
        assert client.post(
            f"/api/orders/{order_id}/review",
            json={"rating": 5, "want_again": "想吃", "comment": "重复"},
        ).status_code == 409

        removed = client.delete(f"/api/dishes/{dish_id}", headers=headers)
        assert removed.status_code == 204
        assert client.get(f"/api/dishes/{dish_id}").status_code == 404

        historical_order = client.get(f"/api/orders/{order_id}")
        assert historical_order.status_code == 200
        assert historical_order.json()["items"][0]["dish_name"] == "CI 测试菜"


def test_realtime_order_event():
    with TestClient(app) as client:
        token = admin_token(client)
        dish_id = client.get("/api/dishes").json()[0]["id"]
        with client.websocket_connect("/ws/admin/orders") as websocket:
            websocket.send_json({"type": "auth", "token": token})
            assert websocket.receive_json()["type"] == "ready"
            response = client.post(
                "/api/orders",
                json={
                    "items": [{"dish_id": dish_id, "quantity": 1}],
                    "customer_id": "gf_realtime_test",
                },
            )
            assert response.status_code == 201
            event = websocket.receive_json()
            assert event == {"type": "order_created", "order_id": response.json()["id"]}


def test_v2_favorites_repeat_dish_metadata_and_ranking():
    with TestClient(app) as client:
        headers = admin_headers(client)
        customer_headers = {"X-Customer-Id": "gf_v2_test"}
        dish_response = client.post(
            "/api/dishes",
            headers=headers,
            json={
                "name": "V2 番茄牛腩",
                "description": "用于验证 V2 完整点菜流程",
                "category": "肉肉",
                "price": 42,
                "image_url": "",
                "cook_time": 45,
                "difficulty": 3,
                "spicy_level": 0,
                "tags": ["下饭", "暖胃"],
            },
        )
        assert dish_response.status_code == 201
        dish = dish_response.json()
        dish_id = dish["id"]
        assert dish["cook_time"] == 45
        assert dish["tags"] == ["下饭", "暖胃"]

        assert client.get("/api/favorites").status_code == 400
        assert client.post(
            f"/api/favorites/{dish_id}", headers=customer_headers
        ).status_code == 200
        favorites = client.get("/api/favorites", headers=customer_headers)
        assert [item["id"] for item in favorites.json()] == [dish_id]

        first_order = client.post(
            "/api/orders",
            json={
                "items": [{"dish_id": dish_id, "quantity": 1}],
                "note": "少盐",
                "customer_id": "gf_v2_test",
            },
        )
        assert first_order.status_code == 201
        first_order_id = first_order.json()["id"]

        assert client.post(
            f"/api/orders/repeat/{first_order_id}",
            headers={"X-Customer-Id": "gf_someone_else"},
        ).status_code == 403
        draft = client.post(
            f"/api/orders/repeat/{first_order_id}", headers=customer_headers
        )
        assert draft.status_code == 200
        assert draft.json()["items"][0]["available"] is True
        assert draft.json()["note"] == "少盐"

        repeated_order = client.post(
            "/api/orders",
            json={
                "items": [{"dish_id": dish_id, "quantity": 2}],
                "customer_id": "gf_v2_test",
                "source_order_id": first_order_id,
            },
        )
        assert repeated_order.status_code == 201
        assert repeated_order.json()["source_order_id"] == first_order_id

        client.patch(
            f"/api/orders/{first_order_id}/status",
            headers=headers,
            json={"status": "已完成"},
        )
        client.post(
            f"/api/orders/{first_order_id}/review",
            json={"rating": 5, "want_again": "想吃", "comment": "暖暖的"},
        )
        ranking = client.get(
            "/api/stats/favorite-ranking", headers=customer_headers
        )
        assert ranking.status_code == 200
        top = ranking.json()[0]
        assert top["dish_id"] == dish_id
        assert top["count"] == 3
        assert top["rating"] == 5.0
        assert top["repeat_count"] == 1
        assert top["is_favorite"] is True

        assert client.delete(
            f"/api/favorites/{dish_id}", headers=customer_headers
        ).status_code == 204
        assert client.get("/api/favorites", headers=customer_headers).json() == []


def test_two_player_dice_room_privacy_and_challenge():
    with TestClient(app) as client:
        room_response = client.post(
            "/api/games/dice/rooms",
            json={"invite_code": "test-invite"},
        )
        assert room_response.status_code == 200
        room_code = room_response.json()["room_code"]

        with client.websocket_connect(f"/ws/games/dice/{room_code}") as first:
            first.send_json({
                "type": "join",
                "player_id": "gf_first",
                "name": "我",
                "invite_code": "test-invite",
            })
            assert first.receive_json()["phase"] == "waiting"
            with client.websocket_connect(f"/ws/games/dice/{room_code}") as second:
                second.send_json({
                    "type": "join",
                    "player_id": "gf_second",
                    "name": "女朋友",
                    "invite_code": "test-invite",
                })
                first_ready = first.receive_json()
                second_ready = second.receive_json()
                assert first_ready["phase"] == second_ready["phase"] == "rolling"

                first.send_json({"type": "roll", "values": [1, 2, 3, 4, 5]})
                first_rolled = first.receive_json()
                second_sees_first = second.receive_json()
                assert first_rolled["my_dice"] == [1, 2, 3, 4, 5]
                assert second_sees_first["my_dice"] is None
                assert second_sees_first["all_dice"] is None

                second.send_json({"type": "roll", "values": [2, 2, 3, 5, 6]})
                first_bidding = first.receive_json()
                second_bidding = second.receive_json()
                assert first_bidding["phase"] == second_bidding["phase"] == "bidding"
                assert first_bidding["turn_id"] == "gf_first"

                first.send_json({"type": "bid", "quantity": 3, "face": 2})
                first.receive_json()
                second_turn = second.receive_json()
                assert second_turn["turn_id"] == "gf_second"
                second.send_json({"type": "challenge"})
                first_finished = first.receive_json()
                second_finished = second.receive_json()
                assert first_finished["phase"] == second_finished["phase"] == "finished"
                assert first_finished["outcome"]["actual_count"] == 4
                assert set(first_finished["all_dice"]) == {"gf_first", "gf_second"}
                assert next(
                    player["score"]
                    for player in first_finished["players"]
                    if player["id"] == first_finished["outcome"]["winner_id"]
                ) == 1

                first.send_json({"type": "rematch"})
                first_waiting = first.receive_json()
                second_waiting = second.receive_json()
                assert first_waiting["phase"] == second_waiting["phase"] == "finished"
                second.send_json({"type": "rematch"})
                first_rematch = first.receive_json()
                second_rematch = second.receive_json()
                assert first_rematch["phase"] == second_rematch["phase"] == "rolling"
                assert first_rematch["round"] == 2
                assert sum(player["score"] for player in first_rematch["players"]) == 1


def test_unified_game_catalog_room_and_websocket_protocol():
    with TestClient(app) as client:
        games = client.get("/api/games")
        assert games.status_code == 200
        catalog = {game["type"]: game for game in games.json()}
        assert catalog["dice"]["status"] == "available"
        assert catalog["gomoku"]["status"] == "available"
        assert client.post(
            "/api/games/rooms",
            json={
                "game_type": "dice",
                "creator": "gf_game_creator",
                "invite_code": "wrong",
            },
        ).status_code == 401

        created = client.post(
            "/api/games/rooms",
            json={
                "game_type": "dice",
                "creator": "gf_game_creator",
                "invite_code": "test-invite",
            },
        )
        assert created.status_code == 201
        room_code = created.json()["room_code"]
        assert created.json()["status"] == "waiting"
        assert created.json()["max_players"] == 2

        def join_message(player_id, name):
            return {
                "type": "join",
                "game": "dice",
                "data": {
                    "player_id": player_id,
                    "name": name,
                    "invite_code": "test-invite",
                },
            }

        with client.websocket_connect(f"/ws/game/{room_code}") as first:
            first.send_json(join_message("gf_unified_first", "我"))
            first_waiting = first.receive_json()
            assert first_waiting["type"] == "state"
            assert first_waiting["game"] == "dice"
            assert first_waiting["data"]["phase"] == "waiting"
            with client.websocket_connect(f"/ws/game/{room_code}") as second:
                second.send_json(join_message("gf_unified_second", "女朋友"))
                assert first.receive_json()["data"]["phase"] == "rolling"
                assert second.receive_json()["data"]["phase"] == "rolling"
                assert client.get(f"/api/games/rooms/{room_code}").json()["status"] == "playing"

                first.send_json({
                    "type": "roll",
                    "game": "dice",
                    "data": {"values": [1, 2, 3, 4, 5]},
                })
                first.receive_json()
                second.receive_json()
                second.send_json({
                    "type": "roll",
                    "game": "dice",
                    "data": {"values": [2, 2, 3, 5, 6]},
                })
                assert first.receive_json()["data"]["phase"] == "bidding"
                assert second.receive_json()["data"]["phase"] == "bidding"

                first.send_json({
                    "type": "bid",
                    "game": "dice",
                    "data": {"quantity": 3, "face": 2},
                })
                first.receive_json()
                second.receive_json()
                second.send_json({"type": "challenge", "game": "dice", "data": {}})
                first_finished = first.receive_json()
                second_finished = second.receive_json()
                assert first_finished["data"]["phase"] == "finished"
                assert second_finished["data"]["outcome"]["actual_count"] == 4
                assert client.get(f"/api/games/rooms/{room_code}").json()["status"] == "finished"
