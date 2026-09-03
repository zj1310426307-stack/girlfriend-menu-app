"""Regression coverage for truthful, idempotent order acknowledgements."""

from unittest.mock import AsyncMock, Mock
import uuid

from fastapi.testclient import TestClient
import pytest

import models
from database import SessionLocal
from main import app
from services import order_service


@pytest.fixture(autouse=True)
def configure_customer_invite(monkeypatch):
    """Provide the explicit test-only invite required by customer authentication."""
    monkeypatch.setenv("CUSTOMER_INVITE_CODE", "test-invite")


def _customer_session(client: TestClient) -> tuple[dict, dict]:
    """Create one isolated customer and return its session plus bearer headers."""
    response = client.post(
        "/api/customers/session",
        json={
            "invite_code": "test-invite",
            "display_name": "她",
            "device_label": "订单安全测试",
        },
    )
    assert response.status_code == 200
    session = response.json()
    return session, {"Authorization": f"Bearer {session['customer_token']}"}


def _order_payload(
    dish_id: int,
    idempotency_key: str,
    *,
    source_order_id: int | None = None,
) -> dict:
    """Build one valid order request with a stable replay identifier."""
    payload = {
        "items": [{"dish_id": dish_id, "quantity": 1}],
        "idempotency_key": idempotency_key,
    }
    if source_order_id:
        payload["source_order_id"] = source_order_id
    return payload


def _assert_one_order(idempotency_key: str) -> models.Order:
    """Load the only order persisted for one idempotency key."""
    with SessionLocal() as db:
        orders = (
            db.query(models.Order)
            .filter(models.Order.idempotency_key == idempotency_key)
            .all()
        )
        assert len(orders) == 1
        order_id = orders[0].id
    with SessionLocal() as db:
        return db.get(models.Order, order_id)


def _admin_order_notification_count(order_id: int) -> int:
    """Count durable ORDER_CREATED notifications for one order."""
    with SessionLocal() as db:
        admin = db.query(models.User).filter(models.User.user_code == "admin").one()
        return (
            db.query(models.Notification)
            .filter(
                models.Notification.user_id == admin.id,
                models.Notification.type == "ORDER_CREATED",
                models.Notification.related_id == order_id,
            )
            .count()
        )


def test_idempotent_replay_keeps_one_notification_and_one_broadcast(monkeypatch):
    """A normal replay returns the original order without repeating user-visible effects."""
    marker = uuid.uuid4().hex
    key = f"order-safety-replay-{marker}"
    broadcast = AsyncMock()
    monkeypatch.setattr(order_service.order_event_hub, "broadcast", broadcast)

    with TestClient(app) as client:
        _, headers = _customer_session(client)
        dish_id = client.get("/api/dishes").json()[0]["id"]
        payload = _order_payload(dish_id, key)
        first = client.post("/api/orders", headers=headers, json=payload)
        replay = client.post("/api/orders", headers=headers, json=payload)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    order = _assert_one_order(key)
    assert _admin_order_notification_count(order.id) == 1
    broadcast.assert_awaited_once_with("order_created", order.id)


def test_notification_failure_returns_created_order_and_replay_repairs_once(
    monkeypatch,
):
    """A transient notification failure never falsifies creation and is replay-repairable."""
    marker = uuid.uuid4().hex
    key = f"order-safety-notification-{marker}"
    original = order_service.notification_service.create_notification_once
    attempts = 0

    def fail_once(*args, **kwargs):
        """Fail the first notification attempt, then delegate to the real writer."""
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic notification failure")
        return original(*args, **kwargs)

    broadcast = AsyncMock()
    logged = Mock()
    monkeypatch.setattr(
        order_service.notification_service,
        "create_notification_once",
        fail_once,
    )
    monkeypatch.setattr(order_service.order_event_hub, "broadcast", broadcast)
    monkeypatch.setattr(order_service.logger, "exception", logged)

    with TestClient(app) as client:
        _, headers = _customer_session(client)
        dish_id = client.get("/api/dishes").json()[0]["id"]
        payload = _order_payload(dish_id, key)
        first = client.post("/api/orders", headers=headers, json=payload)
        replay = client.post("/api/orders", headers=headers, json=payload)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    order = _assert_one_order(key)
    assert _admin_order_notification_count(order.id) == 1
    broadcast.assert_awaited_once_with("order_created", order.id)
    logged.assert_any_call(
        "order_post_commit_effect_failed effect=%s order_id=%s "
        "created=%s compensable=%s",
        "order_created_notification",
        order.id,
        "true",
        "true",
    )


def test_memory_failure_returns_created_order_and_replay_repairs_once(
    monkeypatch,
):
    """A transient first-meal memory failure is logged and repaired by replay."""
    marker = uuid.uuid4().hex
    key = f"order-safety-memory-{marker}"
    original = order_service.couple_profile_service.record_first_memory
    attempts = 0

    def fail_once(*args, **kwargs):
        """Fail the first memory attempt, then delegate to the idempotent writer."""
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic memory failure")
        return original(*args, **kwargs)

    broadcast = AsyncMock()
    logged = Mock()
    monkeypatch.setattr(
        order_service.couple_profile_service,
        "record_first_memory",
        fail_once,
    )
    monkeypatch.setattr(order_service.order_event_hub, "broadcast", broadcast)
    monkeypatch.setattr(order_service.logger, "exception", logged)

    with TestClient(app) as client:
        session, headers = _customer_session(client)
        dish_id = client.get("/api/dishes").json()[0]["id"]
        payload = _order_payload(dish_id, key)
        first = client.post("/api/orders", headers=headers, json=payload)
        replay = client.post("/api/orders", headers=headers, json=payload)

    assert first.status_code == 201
    assert replay.status_code == 201
    order = _assert_one_order(key)
    with SessionLocal() as db:
        user = (
            db.query(models.User)
            .filter(models.User.user_code == session["customer_id"])
            .one()
        )
        memories = (
            db.query(models.CoupleMemory)
            .filter(
                models.CoupleMemory.user_id == user.id,
                models.CoupleMemory.type == "FIRST_MEAL",
            )
            .all()
        )
        assert len(memories) == 1
        assert memories[0].source_id == order.id
    assert _admin_order_notification_count(order.id) == 1
    broadcast.assert_awaited_once_with("order_created", order.id)
    logged.assert_any_call(
        "order_post_commit_effect_failed effect=%s order_id=%s "
        "created=%s compensable=%s",
        "first_meal_memory",
        order.id,
        "true",
        "true",
    )


def test_repeat_reward_failure_returns_created_order_and_replay_repairs_once(
    monkeypatch,
):
    """A transient repeat reward failure is repaired without duplicating the order."""
    marker = uuid.uuid4().hex
    source_key = f"order-safety-source-{marker}"
    repeat_key = f"order-safety-reward-{marker}"

    with TestClient(app) as client:
        session, headers = _customer_session(client)
        dish_id = client.get("/api/dishes").json()[0]["id"]
        source = client.post(
            "/api/orders",
            headers=headers,
            json=_order_payload(dish_id, source_key),
        )
        assert source.status_code == 201

        original = order_service.record_score
        attempts = 0

        def fail_once(*args, **kwargs):
            """Fail the first reward attempt, then delegate to its unique writer."""
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("synthetic repeat reward failure")
            return original(*args, **kwargs)

        broadcast = AsyncMock()
        logged = Mock()
        monkeypatch.setattr(order_service, "record_score", fail_once)
        monkeypatch.setattr(order_service.order_event_hub, "broadcast", broadcast)
        monkeypatch.setattr(order_service.logger, "exception", logged)
        payload = _order_payload(
            dish_id,
            repeat_key,
            source_order_id=source.json()["id"],
        )
        first = client.post("/api/orders", headers=headers, json=payload)
        replay = client.post("/api/orders", headers=headers, json=payload)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    order = _assert_one_order(repeat_key)
    with SessionLocal() as db:
        assert (
            db.query(models.LoveScore)
            .filter(
                models.LoveScore.customer_id == session["customer_id"],
                models.LoveScore.type == "SPECIAL_EVENT",
                models.LoveScore.related_id == order.id,
            )
            .count()
            == 1
        )
    assert _admin_order_notification_count(order.id) == 1
    broadcast.assert_awaited_once_with("order_created", order.id)
    logged.assert_any_call(
        "order_post_commit_effect_failed effect=%s order_id=%s "
        "created=%s compensable=%s",
        "repeat_reward",
        order.id,
        "true",
        "true",
    )


def test_broadcast_failure_returns_created_order_and_is_not_replayed(
    monkeypatch,
):
    """A non-durable broadcast failure is logged but never repeated on HTTP replay."""
    marker = uuid.uuid4().hex
    key = f"order-safety-broadcast-{marker}"
    failed_broadcast = AsyncMock(side_effect=RuntimeError("synthetic broadcast failure"))
    logged = Mock()
    monkeypatch.setattr(
        order_service.order_event_hub,
        "broadcast",
        failed_broadcast,
    )
    monkeypatch.setattr(order_service.logger, "exception", logged)

    with TestClient(app) as client:
        _, headers = _customer_session(client)
        dish_id = client.get("/api/dishes").json()[0]["id"]
        payload = _order_payload(dish_id, key)
        first = client.post("/api/orders", headers=headers, json=payload)
        replay_broadcast = AsyncMock()
        monkeypatch.setattr(
            order_service.order_event_hub,
            "broadcast",
            replay_broadcast,
        )
        replay = client.post("/api/orders", headers=headers, json=payload)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    order = _assert_one_order(key)
    assert _admin_order_notification_count(order.id) == 1
    failed_broadcast.assert_awaited_once_with("order_created", order.id)
    replay_broadcast.assert_not_awaited()
    logged.assert_any_call(
        "order_post_commit_effect_failed effect=order_created_broadcast "
        "order_id=%s created=true compensable=false",
        order.id,
    )
