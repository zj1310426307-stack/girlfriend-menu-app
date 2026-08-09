from fastapi.testclient import TestClient

from test_api import admin_headers, app


def test_love_score_permissions_automatic_triggers_and_persistence():
    customer_id = "gf_couple_score_test"
    customer_headers = {"X-Customer-Id": customer_id}

    with TestClient(app) as client:
        empty = client.get("/api/couple/score", headers=customer_headers)
        assert empty.status_code == 200
        assert empty.json()["points_total"] == 0
        assert empty.json()["level"] == "初识"
        assert client.get("/api/couple/score").status_code == 401

        manual_payload = {
            "type": "SPECIAL_EVENT",
            "score": 20,
            "description": "第一次一起使用情侣中心",
        }
        assert client.post(
            "/api/couple/score/add",
            headers=customer_headers,
            json=manual_payload,
        ).status_code == 401
        protected_headers = {**admin_headers(client), **customer_headers}
        manual = client.post(
            "/api/couple/score/add",
            headers=protected_headers,
            json=manual_payload,
        )
        assert manual.status_code == 201
        assert manual.json()["score"] == 20

        dish = client.post(
            "/api/dishes",
            headers=admin_headers(client),
            json={
                "name": "默契值测试晚餐",
                "description": "验证自动积分",
                "category": "测试",
                "price": 20,
                "image_url": "",
            },
        ).json()
        order = client.post(
            "/api/orders",
            json={
                "items": [{"dish_id": dish["id"], "quantity": 1}],
                "customer_id": customer_id,
            },
        ).json()
        order_id = order["id"]

        admin = admin_headers(client)
        for next_status in ("已接单", "制作中", "已完成"):
            completed = client.patch(
                f"/api/orders/{order_id}/status",
                headers=admin,
                json={"status": next_status},
            )
        assert completed.status_code == 200
        # Repeating the same status transition must not award another +10.
        assert client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin_headers(client),
            json={"status": "已完成"},
        ).status_code == 200

        review = client.post(
            f"/api/orders/{order_id}/review",
            json={"rating": 5, "want_again": "想吃", "comment": "五星"},
        )
        assert review.status_code == 201

        repeated = client.post(
            "/api/orders",
            json={
                "items": [{"dish_id": dish["id"], "quantity": 1}],
                "customer_id": customer_id,
                "source_order_id": order_id,
            },
        )
        assert repeated.status_code == 201

        history = client.get(
            "/api/couple/score/history", headers=customer_headers
        )
        assert history.status_code == 200
        rows = history.json()
        assert len(rows) == 6
        assert sum(row["score"] for row in rows) == 45
        assert {row["type"] for row in rows} == {
            "ORDER_COMPLETE",
            "ORDER_REVIEW",
            "SPECIAL_EVENT",
            "DAILY_TASK",
        }
        assert all(row["time"] for row in rows)

        summary = client.get("/api/couple/score", headers=customer_headers).json()
        assert summary["points_total"] == 45
        assert summary["month_score"] == 45
        assert summary["month_meals"] == 1
        assert summary["month_encouragement"] == 5
        assert summary["total"] > 0
        assert sum(summary["breakdown"].values()) > 0

    # A new application lifespan must read the same ledger from the database.
    with TestClient(app) as client:
        persisted = client.get("/api/couple/score", headers=customer_headers)
        assert persisted.status_code == 200
        assert persisted.json()["points_total"] == 45
