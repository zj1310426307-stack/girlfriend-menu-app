import asyncio
from datetime import timedelta
from io import BytesIO
import time

from fastapi.testclient import TestClient
from PIL import Image

import auth
from test_api import admin_headers, app
import models
from database import SessionLocal
from realtime import GameRoomManager


def _claim(client: TestClient, legacy: str) -> dict:
    response = client.post(
        "/api/customers/claim-legacy",
        json={"invite_code": "test-invite", "legacy_customer_id": legacy, "display_name": "她"},
    )
    assert response.status_code == 200
    return response.json()


def _bearer(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['customer_token']}"}


def test_customer_claim_moves_history_and_blocks_forged_identity(monkeypatch):
    legacy = "gf_v28_legacy_owner"
    with TestClient(app) as client:
        dish_id = client.get("/api/dishes").json()[0]["id"]
        old_order = client.post(
            "/api/orders",
            json={"items": [{"dish_id": dish_id, "quantity": 1}], "customer_id": legacy},
        )
        assert old_order.status_code == 201
        session = _claim(client, legacy)
        assert session["customer_id"] != legacy
        with SessionLocal() as db:
            assert session["customer_token"] not in str(db.query(models.Customer.token_hash).all())

        monkeypatch.setenv("ALLOW_LEGACY_CUSTOMER_HEADER", "false")
        assert client.get("/api/orders/me", headers={"X-Customer-Id": legacy}).status_code == 401
        mine = client.get("/api/orders/me", headers=_bearer(session))
        assert mine.status_code == 200
        assert [item["id"] for item in mine.json()] == [old_order.json()["id"]]

        stranger = client.post(
            "/api/customers/session",
            json={"invite_code": "test-invite", "display_name": "另一台设备"},
        ).json()
        assert client.get(
            f"/api/orders/{old_order.json()['id']}", headers=_bearer(stranger)
        ).status_code == 404
        assert client.post(
            f"/api/orders/{old_order.json()['id']}/repeat-preview", headers=_bearer(stranger)
        ).status_code == 404
        assert client.post(
            f"/api/orders/{old_order.json()['id']}/review",
            headers=_bearer(stranger),
            json={"rating": 5, "want_again": "想吃", "comment": "不应成功"},
        ).status_code == 404
        assert client.post(
            "/api/customers/claim-legacy",
            json={"invite_code": "test-invite", "legacy_customer_id": legacy, "display_name": "重复"},
        ).status_code == 409


def test_customer_refresh_rotates_token(monkeypatch):
    monkeypatch.setenv("ALLOW_LEGACY_CUSTOMER_HEADER", "false")
    with TestClient(app) as client:
        session = client.post(
            "/api/customers/session",
            json={"invite_code": "test-invite", "display_name": "她"},
        ).json()
        refreshed = client.post("/api/customers/refresh", headers=_bearer(session))
        assert refreshed.status_code == 200
        assert refreshed.json()["customer_token"] != session["customer_token"]
        assert client.get("/api/orders/me", headers=_bearer(session)).status_code == 401
        assert client.get("/api/orders/me", headers=_bearer(refreshed.json())).status_code == 200


def test_signed_admin_token_expires(monkeypatch):
    with TestClient(app) as client:
        token = client.post(
            "/api/admin/login",
            json={"password": "test-password", "invite_code": "test-invite"},
        ).json()["token"]
        assert client.get("/api/admin/orders", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        original_now = auth.utc_now
        monkeypatch.setattr(auth, "utc_now", lambda: original_now() + timedelta(hours=13))
        assert client.get("/api/admin/orders", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_order_idempotency_status_audit_and_admin_pagination(monkeypatch):
    monkeypatch.setenv("ALLOW_LEGACY_CUSTOMER_HEADER", "false")
    with TestClient(app) as client:
        session = client.post(
            "/api/customers/session",
            json={"invite_code": "test-invite", "display_name": "她"},
        ).json()
        customer = _bearer(session)
        admin = admin_headers(client)
        dish_id = client.get("/api/dishes").json()[0]["id"]
        payload = {
            "items": [{"dish_id": dish_id, "quantity": 1}],
            "idempotency_key": "v28_idempotency_000001",
            "desired_at": "2026-08-10T18:30:00+08:00",
        }
        first = client.post("/api/orders", headers=customer, json=payload)
        retried = client.post("/api/orders", headers=customer, json=payload)
        assert first.status_code == 201
        assert retried.status_code == 201
        assert retried.json()["id"] == first.json()["id"]
        assert first.json()["desired_at"].startswith("2026-08-10T10:30:00")
        assert first.json()["status_updated_at"]
        order_id = first.json()["id"]
        assert client.patch(
            f"/api/orders/{order_id}/status", headers=admin, json={"status": "已完成"}
        ).status_code == 409
        for next_status in ("已接单", "制作中", "已完成"):
            assert client.patch(
                f"/api/orders/{order_id}/status", headers=admin, json={"status": next_status}
            ).status_code == 200
        assert client.post(f"/api/admin/orders/{order_id}/rollback", headers=admin).status_code == 409
        with SessionLocal() as db:
            events = db.query(models.OrderStatusEvent).filter_by(order_id=order_id).all()
            assert [event.to_status for event in events] == ["已接单", "制作中", "已完成"]
        page = client.get("/api/admin/orders?limit=1&keyword=1", headers=admin)
        assert page.status_code == 200
        assert len(page.json()["items"]) <= 1
        assert "next_cursor" in page.json()


def test_upload_rejects_extension_disguise_and_reencodes_image(monkeypatch):
    monkeypatch.setenv("UPLOAD_PROVIDER", "local")
    monkeypatch.setenv("APP_ENV", "test")
    with TestClient(app) as client:
        admin = admin_headers(client)
        disguised = client.post(
            "/api/upload/image",
            headers=admin,
            files={"file": ("fake.png", b"not-an-image", "image/png")},
        )
        assert disguised.status_code == 400

        raw = BytesIO()
        image = Image.new("RGB", (8, 8), color=(143, 185, 150))
        image.save(raw, "PNG")
        uploaded = client.post(
            "/api/upload/image",
            headers=admin,
            files={"file": ("dish.png", raw.getvalue(), "image/png")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["image_url"].startswith("/uploads/")

        oversized = client.post(
            "/api/upload/image",
            headers=admin,
            files={"file": ("large.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
        )
        assert oversized.status_code == 413

        monkeypatch.setenv("UPLOAD_PROVIDER", "s3")
        for name in (
            "S3_BUCKET",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
            "S3_PUBLIC_BASE_URL",
        ):
            monkeypatch.delenv(name, raising=False)
        unavailable = client.post(
            "/api/upload/image",
            headers=admin,
            files={"file": ("dish.png", raw.getvalue(), "image/png")},
        )
        assert unavailable.status_code == 503


def test_inactive_game_room_hot_state_expires():
    async def scenario():
        manager = GameRoomManager()
        room_code = await manager.create_room(game_type="dice")
        manager.rooms[room_code]["last_activity_at"] = time.time() - 901
        removed = await manager.cleanup_expired(ttl_seconds=900)
        assert removed == [room_code]
        assert not await manager.has_room(room_code)

    asyncio.run(scenario())
