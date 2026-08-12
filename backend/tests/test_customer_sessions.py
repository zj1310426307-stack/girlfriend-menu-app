"""Phase 1 regression tests for recovery, expiry, rotation and invite isolation."""

from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

from fastapi.testclient import TestClient

from test_api import app
from auth import hash_token
import api.dependencies as api_dependencies
import customer_service
import models
from core.rate_limit import MemoryRateLimiter
from database import SessionLocal


def _bearer(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['customer_token']}"}


def _recover(client: TestClient, legacy: str, invite: str = "test-invite"):
    return client.post(
        "/api/customers/recover",
        json={
            "invite_code": invite,
            "legacy_customer_id": legacy,
            "display_name": "她",
            "device_label": "测试微信",
        },
    )


def test_new_customer_session_expires_and_can_be_revoked(monkeypatch):
    monkeypatch.setenv("CUSTOMER_SESSION_TTL_DAYS", "30")
    with TestClient(app) as client:
        response = client.post(
            "/api/customers/session",
            json={"invite_code": "test-invite", "display_name": "她", "device_label": "测试设备"},
        )
        assert response.status_code == 200
        session = response.json()
        assert session["expires_at"]
        with SessionLocal() as db:
            stored = db.query(models.CustomerSession).filter_by(customer_id=session["customer_id"]).one()
            assert stored.device_label == "测试设备"
            assert stored.revoked_at is None

        assert client.get("/api/orders/me", headers=_bearer(session)).status_code == 200
        assert client.post("/api/customers/revoke", headers=_bearer(session)).status_code == 204
        assert client.get("/api/orders/me", headers=_bearer(session)).status_code == 401


def test_expired_session_is_rejected(monkeypatch):
    with TestClient(app) as client:
        session = client.post(
            "/api/customers/session",
            json={"invite_code": "test-invite", "display_name": "她"},
        ).json()
        with SessionLocal() as db:
            stored = db.query(models.CustomerSession).filter_by(customer_id=session["customer_id"]).one()
            stored.expires_at = customer_service.utc_now() - timedelta(seconds=1)
            db.commit()
        assert client.get("/api/orders/me", headers=_bearer(session)).status_code == 401


def test_recovery_restores_same_identity_rotates_token_and_preserves_history():
    legacy = f"gf_recovery_{uuid.uuid4().hex[:12]}"
    with TestClient(app) as client:
        dish_id = client.get("/api/dishes").json()[0]["id"]
        old_order = client.post(
            "/api/orders",
            json={"items": [{"dish_id": dish_id, "quantity": 1}], "customer_id": legacy},
        ).json()
        with SessionLocal() as db:
            db.add(models.FavoriteDish(customer_id=legacy, dish_id=dish_id))
            db.add(
                models.LoveScore(
                    customer_id=legacy,
                    score=5,
                    type="SPECIAL_EVENT",
                    description="恢复测试",
                    related_id=991001,
                )
            )
            room = models.GameRoom(
                room_code=f"R{uuid.uuid4().hex[:7].upper()}",
                game_type="gomoku",
                creator=legacy,
                status="finished",
                max_players=2,
            )
            db.add(room)
            db.flush()
            db.add(models.GamePlayer(room_id=room.id, player_id=legacy, seat=1))
            db.add(
                models.GameRecord(
                    room_id=room.id,
                    round_number=1,
                    game_type="gomoku",
                    winner=legacy,
                    duration=30,
                    result={"winner": legacy},
                )
            )
            db.commit()

        first = _recover(client, legacy)
        assert first.status_code == 200
        first_session = first.json()
        recovered = _recover(client, legacy)
        assert recovered.status_code == 200
        second_session = recovered.json()
        assert second_session["customer_id"] == first_session["customer_id"]
        assert second_session["customer_token"] != first_session["customer_token"]
        assert client.get("/api/orders/me", headers=_bearer(first_session)).status_code == 401

        history = client.get("/api/orders/me", headers=_bearer(second_session))
        assert [item["id"] for item in history.json()] == [old_order["id"]]
        with SessionLocal() as db:
            customer_id = second_session["customer_id"]
            assert db.query(models.Customer).filter_by(legacy_customer_id=legacy).count() == 1
            assert db.query(models.FavoriteDish).filter_by(customer_id=customer_id).count() == 1
            assert db.query(models.LoveScore).filter_by(customer_id=customer_id).count() == 1
            assert db.query(models.GamePlayer).filter_by(player_id=customer_id).count() == 1
            assert db.query(models.GameRecord).filter_by(winner=customer_id).count() == 1
            sessions = db.query(models.CustomerSession).filter_by(customer_id=customer_id).all()
            assert len(sessions) == 2
            assert sum(item.revoked_at is None for item in sessions) == 1


def test_recovery_rejects_wrong_invite_and_is_rate_limited(monkeypatch):
    monkeypatch.setattr(api_dependencies, "rate_limiter", MemoryRateLimiter())
    legacy = f"gf_recovery_rate_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        for _ in range(5):
            assert _recover(client, legacy, "wrong-invite").status_code == 401
        limited = _recover(client, legacy, "wrong-invite")
        assert limited.status_code == 429


def test_customer_invite_never_falls_back_to_admin_invite(monkeypatch):
    monkeypatch.delenv("CUSTOMER_INVITE_CODE", raising=False)
    monkeypatch.setenv("ADMIN_INVITE_CODE", "admin-only-secret")
    with TestClient(app) as client:
        response = client.post(
            "/api/customers/session",
            json={"invite_code": "admin-only-secret", "display_name": "她"},
        )
        assert response.status_code == 503


def test_refresh_rotates_session_chain_and_invalidates_previous_token():
    with TestClient(app) as client:
        original = client.post(
            "/api/customers/session",
            json={"invite_code": "test-invite", "display_name": "她"},
        ).json()
        refreshed = client.post("/api/customers/refresh", headers=_bearer(original))
        assert refreshed.status_code == 200
        replacement = refreshed.json()
        assert client.get("/api/orders/me", headers=_bearer(original)).status_code == 401
        assert client.get("/api/orders/me", headers=_bearer(replacement)).status_code == 200
        with SessionLocal() as db:
            sessions = (
                db.query(models.CustomerSession)
                .filter_by(customer_id=original["customer_id"])
                .order_by(models.CustomerSession.id)
                .all()
            )
            assert len(sessions) == 2
            assert sessions[0].revoked_at is not None
            assert sessions[1].rotated_from_id == sessions[0].id


def test_pre_phase1_customer_hash_is_lazily_bridged_to_expiring_session():
    customer_id = f"gf_bridge_{uuid.uuid4().hex[:12]}"
    raw_token = f"gft_bridge_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    with SessionLocal() as db:
        db.add(
            models.Customer(
                id=customer_id,
                token_hash=hash_token(raw_token),
                display_name="旧版本设备",
            )
        )
        db.commit()
        assert db.query(models.CustomerSession).filter_by(customer_id=customer_id).count() == 0

    with TestClient(app) as client:
        response = client.get(
            "/api/orders/me",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == 200
    with SessionLocal() as db:
        bridged = db.query(models.CustomerSession).filter_by(customer_id=customer_id).one()
        assert bridged.device_label == "legacy-token"
        assert bridged.expires_at is not None


def test_concurrent_first_recovery_keeps_one_customer_identity():
    legacy = f"gf_concurrent_{uuid.uuid4().hex[:12]}"
    barrier = Barrier(2)

    def recover_once():
        with SessionLocal() as db:
            barrier.wait(timeout=5)
            return customer_service.recover_legacy(
                db,
                "test-invite",
                legacy,
                "她",
                "并发测试",
            )

    with TestClient(app):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: recover_once(), range(2)))

    assert {item["customer_id"] for item in results} == {results[0]["customer_id"]}
    with SessionLocal() as db:
        assert db.query(models.Customer).filter_by(legacy_customer_id=legacy).count() == 1
