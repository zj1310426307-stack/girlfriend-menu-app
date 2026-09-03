"""Regression coverage for truthful, replay-safe order mutations and reviews."""

from unittest.mock import AsyncMock, Mock
import uuid

from fastapi.testclient import TestClient
import pytest

import models
from database import SessionLocal
from main import app
from services import order_service, review_service
from test_api import admin_headers


@pytest.fixture(autouse=True)
def configure_customer_invite(monkeypatch):
    """Provide the explicit test invite required by customer authentication."""
    monkeypatch.setenv("CUSTOMER_INVITE_CODE", "test-invite")


def _customer_order(client: TestClient) -> tuple[int, str, dict]:
    """Create an isolated authenticated customer order for mutation tests."""
    session = client.post(
        "/api/customers/session",
        json={
            "invite_code": "test-invite",
            "display_name": "她",
            "device_label": "订单变更安全测试",
        },
    ).json()
    headers = {"Authorization": f"Bearer {session['customer_token']}"}
    dish_id = client.get("/api/dishes").json()[0]["id"]
    response = client.post(
        "/api/orders",
        headers=headers,
        json={
            "items": [{"dish_id": dish_id, "quantity": 1}],
            "idempotency_key": f"mutation-safety-{uuid.uuid4().hex}",
        },
    )
    assert response.status_code == 201
    return response.json()["id"], session["customer_id"], headers


def _fail_once(delegate):
    """Return a callable that raises once before delegating future attempts."""
    attempts = {"count": 0}

    def wrapped(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("synthetic committed-effect failure")
        return delegate(*args, **kwargs)

    wrapped.attempts = attempts
    return wrapped


def test_completed_status_acknowledges_failures_and_replay_repairs_safe_effects(
    monkeypatch,
):
    """Completion stays 200 and a same-status replay repairs only safe effects."""
    with TestClient(app) as client:
        order_id, customer_id, _ = _customer_order(client)
        admin = admin_headers(client)
        assert client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin,
            json={"status": "已接单", "expected_status": "待接单"},
        ).status_code == 200
        assert client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin,
            json={"status": "制作中", "expected_status": "已接单"},
        ).status_code == 200

        score = _fail_once(order_service.record_score)
        memory = _fail_once(order_service.couple_profile_service.record_first_memory)
        task = _fail_once(order_service.complete_task_type)
        notification = _fail_once(
            order_service.notification_service.create_notification,
        )
        broadcast = AsyncMock(side_effect=RuntimeError("synthetic broadcast failure"))
        monkeypatch.setattr(order_service, "record_score", score)
        monkeypatch.setattr(
            order_service.couple_profile_service,
            "record_first_memory",
            memory,
        )
        monkeypatch.setattr(order_service, "complete_task_type", task)
        monkeypatch.setattr(
            order_service.notification_service,
            "create_notification",
            notification,
        )
        monkeypatch.setattr(order_service.order_event_hub, "broadcast", broadcast)

        first = client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin,
            json={"status": "已完成", "expected_status": "制作中"},
        )
        replay = client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin,
            json={"status": "已完成", "expected_status": "制作中"},
        )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["status"] == replay.json()["status"] == "已完成"
    assert score.attempts["count"] == 2
    assert memory.attempts["count"] == 2
    assert task.attempts["count"] == 2
    assert notification.attempts["count"] == 1
    broadcast.assert_awaited_once_with("order_status_changed", order_id)

    with SessionLocal() as db:
        assert (
            db.query(models.OrderStatusEvent)
            .filter_by(order_id=order_id, to_status="已完成")
            .count()
            == 1
        )
        assert (
            db.query(models.LoveScore)
            .filter_by(
                customer_id=customer_id,
                type="ORDER_COMPLETE",
                related_id=order_id,
            )
            .count()
            == 1
        )
        assert (
            db.query(models.DailyTask)
            .filter_by(customer_id=customer_id, type="MEAL", status="completed")
            .count()
            == 1
        )
        user = db.query(models.User).filter_by(user_code=customer_id).one()
        assert (
            db.query(models.CoupleMemory)
            .filter_by(user_id=user.id, type="FIRST_COOK")
            .count()
            == 1
        )


def test_stale_status_write_conflicts_without_audit_or_side_effects(monkeypatch):
    """A second administrator cannot overwrite a status chosen from stale state."""
    with TestClient(app) as client:
        order_id, _, _ = _customer_order(client)
        admin = admin_headers(client)
        notification = Mock()
        broadcast = AsyncMock()
        monkeypatch.setattr(
            order_service.notification_service,
            "create_notification",
            notification,
        )
        monkeypatch.setattr(order_service.order_event_hub, "broadcast", broadcast)

        accepted = client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin,
            json={"status": "已接单", "expected_status": "待接单"},
        )
        stale = client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin,
            json={"status": "暂时做不了", "expected_status": "待接单"},
        )

    assert accepted.status_code == 200
    assert stale.status_code == 409
    assert "待接单" in stale.json()["detail"]
    assert "已接单" in stale.json()["detail"]
    notification.assert_called_once()
    broadcast.assert_awaited_once_with("order_status_changed", order_id)
    with SessionLocal() as db:
        assert db.get(models.Order, order_id).status == "已接单"
        assert (
            db.query(models.OrderStatusEvent)
            .filter_by(order_id=order_id)
            .count()
            == 1
        )


def test_rollback_expected_state_and_legacy_retry_never_flip_forward(monkeypatch):
    """Rollback retries cannot undo the rollback, while new guarded rolls can continue."""
    broadcast = AsyncMock(side_effect=RuntimeError("synthetic broadcast failure"))
    monkeypatch.setattr(order_service.order_event_hub, "broadcast", broadcast)
    with TestClient(app) as client:
        order_id, _, _ = _customer_order(client)
        admin = admin_headers(client)
        for current, target in (("待接单", "已接单"), ("已接单", "制作中")):
            assert client.patch(
                f"/api/orders/{order_id}/status",
                headers=admin,
                json={"status": target, "expected_status": current},
            ).status_code == 200

        first = client.post(
            f"/api/admin/orders/{order_id}/rollback",
            headers=admin,
            json={"expected_status": "制作中"},
        )
        stale_retry = client.post(
            f"/api/admin/orders/{order_id}/rollback",
            headers=admin,
            json={"expected_status": "制作中"},
        )
        second = client.post(
            f"/api/admin/orders/{order_id}/rollback",
            headers=admin,
            json={"expected_status": "已接单"},
        )

        legacy_id, _, _ = _customer_order(client)
        for target in ("已接单", "制作中"):
            assert client.patch(
                f"/api/orders/{legacy_id}/status",
                headers=admin,
                json={"status": target},
            ).status_code == 200
        legacy_first = client.post(
            f"/api/admin/orders/{legacy_id}/rollback",
            headers=admin,
        )
        legacy_retry = client.post(
            f"/api/admin/orders/{legacy_id}/rollback",
            headers=admin,
        )

    assert first.status_code == 200 and first.json()["status"] == "已接单"
    assert stale_retry.status_code == 409
    assert "制作中" in stale_retry.json()["detail"]
    assert "已接单" in stale_retry.json()["detail"]
    assert second.status_code == 200 and second.json()["status"] == "待接单"
    assert legacy_first.status_code == 200
    assert legacy_retry.status_code == 200
    assert legacy_first.json()["status"] == legacy_retry.json()["status"] == "已接单"
    with SessionLocal() as db:
        assert (
            db.query(models.OrderStatusEvent)
            .filter_by(order_id=legacy_id, actor_type="ADMIN_ROLLBACK")
            .count()
            == 1
        )


def test_review_exact_replay_repairs_effects_without_duplicate_or_broadcast(
    monkeypatch,
):
    """An exact review retry repairs safe effects and changed feedback remains 409."""
    with TestClient(app) as client:
        order_id, customer_id, customer = _customer_order(client)
        admin = admin_headers(client)
        for current, target in (
            ("待接单", "已接单"),
            ("已接单", "制作中"),
            ("制作中", "已完成"),
        ):
            assert client.patch(
                f"/api/orders/{order_id}/status",
                headers=admin,
                json={"status": target, "expected_status": current},
            ).status_code == 200

        score = _fail_once(review_service.record_score)
        task = _fail_once(review_service.complete_task_type)
        notification = _fail_once(
            review_service.notification_service.create_notification_once,
        )
        broadcast = AsyncMock(side_effect=RuntimeError("synthetic broadcast failure"))
        monkeypatch.setattr(review_service, "record_score", score)
        monkeypatch.setattr(review_service, "complete_task_type", task)
        monkeypatch.setattr(
            review_service.notification_service,
            "create_notification_once",
            notification,
        )
        monkeypatch.setattr(review_service.order_event_hub, "broadcast", broadcast)
        payload = {"rating": 5, "want_again": "想吃", "comment": "很好吃"}
        first = client.post(
            f"/api/orders/{order_id}/review",
            headers=customer,
            json=payload,
        )
        replay = client.post(
            f"/api/orders/{order_id}/review",
            headers=customer,
            json=payload,
        )
        conflict = client.post(
            f"/api/orders/{order_id}/review",
            headers=customer,
            json={**payload, "comment": "改过的评价"},
        )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert conflict.status_code == 409
    assert score.attempts["count"] == 2
    assert task.attempts["count"] == 2
    assert notification.attempts["count"] == 2
    broadcast.assert_awaited_once_with("order_reviewed", order_id)
    with SessionLocal() as db:
        assert db.query(models.Review).filter_by(order_id=order_id).count() == 1
        assert (
            db.query(models.LoveScore)
            .filter_by(
                customer_id=customer_id,
                type="ORDER_REVIEW",
                related_id=order_id,
            )
            .count()
            == 1
        )
        admin_user = db.query(models.User).filter_by(user_code="admin").one()
        assert (
            db.query(models.Notification)
            .filter_by(
                user_id=admin_user.id,
                type="ORDER_REVIEW",
                related_id=order_id,
            )
            .count()
            == 1
        )
