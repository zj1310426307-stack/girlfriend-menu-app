"""Behavior contracts for the Phase 2B Review, Order and Stats boundaries."""

from datetime import date
from unittest.mock import AsyncMock, Mock
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from test_api import admin_headers, app

import models
import schemas
from api.routes import orders as orders_route
from database import Base, SessionLocal, engine
from services import dish_service, order_service, review_service, stats_service


@pytest.fixture(scope="module", autouse=True)
def service_schema():
    """Create the shared SQLite schema when this contract file runs alone."""
    Base.metadata.create_all(bind=engine)


def _dish(db, marker: str, *, active: bool = True) -> models.Dish:
    """Create one unique dish suitable for isolated service-contract tests."""
    dish = dish_service.create_dish(
        db,
        schemas.DishCreate(
            name=f"phase2b-dish-{marker}",
            description="Phase 2B Round 2 contract",
            category="phase2b",
            price=28.0,
            image_url="",
        ),
    )
    if not active:
        dish.is_active = False
        db.commit()
        db.refresh(dish)
    return dish


def _order_data(
    dish_id: int,
    customer_id: str,
    **updates,
) -> schemas.OrderCreate:
    """Build a one-item order payload while allowing focused field overrides."""
    payload = {
        "items": [schemas.OrderItemCreate(dish_id=dish_id, quantity=2)],
        "customer_id": customer_id,
    }
    payload.update(updates)
    return schemas.OrderCreate(**payload)


def _complete(db, order_id: int) -> models.Order:
    """Advance an order through every legal transition to completion."""
    for status in ("已接单", "制作中", "已完成"):
        order = order_service.update_order_status(db, order_id, status)
    return order


def test_review_service_preserves_validation_integrity_and_reward_order(monkeypatch):
    """Review validation precedes persistence and five-star side effects run once."""
    marker = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        dish = _dish(db, marker)
        order = order_service.create_order(
            db,
            _order_data(dish.id, f"gf_review_{marker}"),
        )
        with pytest.raises(HTTPException) as early:
            review_service.create_review(
                db,
                order.id,
                schemas.ReviewCreate(rating=5, want_again="想吃", comment=""),
            )
        assert early.value.status_code == 400

        _complete(db, order.id)
        reward = Mock()
        task = Mock()
        monkeypatch.setattr(review_service, "record_score", reward)
        monkeypatch.setattr(review_service, "complete_task_type", task)
        review = review_service.create_review(
            db,
            order.id,
            schemas.ReviewCreate(rating=5, want_again="想吃", comment="很好吃"),
        )
        assert review.rating == 5
        reward.assert_called_once_with(
            db,
            order.customer_id,
            "ORDER_REVIEW",
            5,
            "完成一次五星评价",
            order.id,
        )
        task.assert_called_once_with(db, order.customer_id, "REVIEW")

        with pytest.raises(HTTPException) as duplicate:
            review_service.create_review(
                db,
                order.id,
                schemas.ReviewCreate(rating=4, want_again="一般", comment=""),
            )
        assert duplicate.value.status_code == 409
        assert reward.call_count == 1
        assert task.call_count == 1


def test_review_service_maps_repository_integrity_error_and_skips_non_five_reward(
    monkeypatch,
):
    """A racing duplicate remains 409 and ordinary ratings do not earn five-star points."""
    marker = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        dish = _dish(db, marker)
        first = order_service.create_order(db, _order_data(dish.id, f"gf_race_{marker}"))
        second = order_service.create_order(db, _order_data(dish.id, f"gf_four_{marker}"))
        _complete(db, first.id)
        _complete(db, second.id)

        monkeypatch.setattr(review_service, "record_score", Mock())
        monkeypatch.setattr(review_service, "complete_task_type", Mock())
        review_service.create_review(
            db,
            second.id,
            schemas.ReviewCreate(rating=4, want_again="一般", comment=""),
        )
        review_service.record_score.assert_not_called()
        review_service.complete_task_type.assert_not_called()

        def raise_integrity(*_args, **_kwargs):
            raise IntegrityError("insert review", {}, Exception("unique"))

        monkeypatch.setattr(review_service.reviews_repository, "create", raise_integrity)
        with pytest.raises(HTTPException) as conflict:
            review_service.create_review(
                db,
                first.id,
                schemas.ReviewCreate(rating=3, want_again="一般", comment=""),
            )
        assert conflict.value.status_code == 409


def test_order_service_preserves_idempotency_snapshot_repeat_and_isolation(monkeypatch):
    """Creation safeguards, immutable snapshots and repeat rules survive extraction."""
    marker = uuid.uuid4().hex[:10]
    owner = f"gf_order_owner_{marker}"
    stranger = f"gf_order_stranger_{marker}"
    with SessionLocal() as db:
        dish = _dish(db, marker)
        key = f"phase2b-{marker}"
        payload = _order_data(dish.id, owner, idempotency_key=key)
        first = order_service.create_order(db, payload)
        assert order_service.create_order(db, payload).id == first.id
        with pytest.raises(HTTPException) as key_conflict:
            order_service.create_order(
                db,
                _order_data(dish.id, stranger, idempotency_key=key),
            )
        assert key_conflict.value.status_code == 409

        snapshot_name = first.items[0].dish_name
        snapshot_price = first.items[0].price
        dish.name = f"changed-{marker}"
        dish.price = 99.0
        db.commit()
        db.expire_all()
        stored = order_service.get_order(db, first.id)
        assert stored.items[0].dish_name == snapshot_name
        assert stored.items[0].price == snapshot_price

        with pytest.raises(HTTPException) as missing:
            order_service.create_order(db, _order_data(999999999, owner))
        assert missing.value.status_code == 400
        inactive = _dish(db, f"inactive-{marker}", active=False)
        with pytest.raises(HTTPException) as disabled:
            order_service.create_order(db, _order_data(inactive.id, owner))
        assert disabled.value.status_code == 400

        with pytest.raises(HTTPException) as hidden_source:
            order_service.create_order(
                db,
                _order_data(dish.id, stranger, source_order_id=first.id),
            )
        assert hidden_source.value.status_code == 404

        score = Mock()
        monkeypatch.setattr(order_service, "record_score", score)
        repeated = order_service.create_order(
            db,
            _order_data(dish.id, owner, source_order_id=first.id),
        )
        score.assert_called_once_with(
            db,
            owner,
            "SPECIAL_EVENT",
            2,
            "再次点了喜欢的菜单",
            repeated.id,
        )
        before = db.query(func.count(models.Order.id)).scalar()
        draft = order_service.repeat_order_draft(db, first.id, owner)
        after = db.query(func.count(models.Order.id)).scalar()
        assert draft["source_order_id"] == first.id
        assert before == after
        assert repeated.id in {
            item.id for item in order_service.list_customer_orders(db, owner)
        }
        assert order_service.list_customer_orders(db, f"absent-{marker}") == []


def test_order_service_preserves_pagination_transition_audit_reward_and_rollback(
    monkeypatch,
):
    """Admin reads and state transitions retain filtering, rewards and append-only audit."""
    marker = uuid.uuid4().hex[:10]
    customer = f"gf_status_{marker}"
    with SessionLocal() as db:
        dish = _dish(db, marker)
        order = order_service.create_order(db, _order_data(dish.id, customer))
        page = order_service.list_admin_orders(
            db,
            cursor=None,
            limit=1,
            keyword=str(order.id),
            start_date=date.today(),
            end_date=date.today(),
        )
        assert [item.id for item in page["items"]] == [order.id]
        assert page["total_estimate"] >= 1

        reward = Mock()
        task = Mock()
        monkeypatch.setattr(order_service, "record_score", reward)
        monkeypatch.setattr(order_service, "complete_task_type", task)
        with pytest.raises(HTTPException) as illegal:
            order_service.update_order_status(db, order.id, "已完成")
        assert illegal.value.status_code == 409

        accepted = order_service.update_order_status(db, order.id, "已接单")
        event_count = db.query(models.OrderStatusEvent).filter_by(order_id=order.id).count()
        assert order_service.update_order_status(db, order.id, "已接单").id == accepted.id
        assert db.query(models.OrderStatusEvent).filter_by(order_id=order.id).count() == event_count

        order_service.update_order_status(db, order.id, "制作中")
        completed = order_service.update_order_status(db, order.id, "已完成")
        reward.assert_called_once_with(
            db,
            customer,
            "ORDER_COMPLETE",
            10,
            "完成一次晚餐制作",
            completed.id,
        )
        task.assert_called_once_with(db, customer, "MEAL")
        order_service.update_order_status(db, order.id, "已完成")
        assert reward.call_count == 1
        assert task.call_count == 1
        with pytest.raises(HTTPException) as blocked:
            order_service.rollback_order_status(db, order.id)
        assert blocked.value.status_code == 409

        rollback_target = order_service.create_order(db, _order_data(dish.id, customer))
        order_service.update_order_status(db, rollback_target.id, "已接单")
        order_service.update_order_status(db, rollback_target.id, "制作中")
        rolled_back = order_service.rollback_order_status(db, rollback_target.id)
        assert rolled_back.status == "已接单"
        latest = (
            db.query(models.OrderStatusEvent)
            .filter_by(order_id=rollback_target.id)
            .order_by(models.OrderStatusEvent.id.desc())
            .first()
        )
        assert latest.actor_type == "ADMIN_ROLLBACK"


def test_review_router_keeps_notification_and_broadcast_once(monkeypatch):
    """The HTTP route keeps post-review notification and WebSocket orchestration."""
    marker = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        dish = _dish(db, marker)
        order = order_service.create_order(db, _order_data(dish.id, f"gf_route_{marker}"))
        _complete(db, order.id)
        order_id = order.id

    notification = Mock()
    broadcast = AsyncMock()
    monkeypatch.setattr(
        orders_route.notification_service,
        "create_notification",
        notification,
    )
    monkeypatch.setattr(orders_route.order_event_hub, "broadcast", broadcast)
    with TestClient(app) as client:
        response = client.post(
            f"/api/orders/{order_id}/review",
            json={"rating": 4, "want_again": "一般", "comment": "保留路由副作用"},
        )
    assert response.status_code == 201
    assert notification.call_count == 1
    broadcast.assert_awaited_once_with("order_reviewed", order_id)


def test_order_status_router_keeps_notification_memory_and_broadcast(monkeypatch):
    """Status and rollback routes retain their exact post-service orchestration."""
    marker = uuid.uuid4().hex[:10]
    customer_id = f"gf_status_route_{marker}"
    with SessionLocal() as db:
        dish = _dish(db, marker)
        completed_target = order_service.create_order(
            db,
            _order_data(dish.id, customer_id),
        )
        rollback_target = order_service.create_order(
            db,
            _order_data(dish.id, customer_id),
        )
        completed_id = completed_target.id
        rollback_id = rollback_target.id

    notification = Mock()
    memory = Mock()
    broadcast = AsyncMock()
    monkeypatch.setattr(
        orders_route.notification_service,
        "create_notification",
        notification,
    )
    monkeypatch.setattr(
        orders_route.couple_profile_service,
        "record_first_memory",
        memory,
    )
    monkeypatch.setattr(orders_route.order_event_hub, "broadcast", broadcast)

    with TestClient(app) as client:
        admin = admin_headers(client)
        for next_status in ("已接单", "制作中", "已完成"):
            response = client.patch(
                f"/api/orders/{completed_id}/status",
                headers=admin,
                json={"status": next_status},
            )
            assert response.status_code == 200
        for next_status in ("已接单", "制作中"):
            response = client.patch(
                f"/api/orders/{rollback_id}/status",
                headers=admin,
                json={"status": next_status},
            )
            assert response.status_code == 200
        rollback = client.post(
            f"/api/admin/orders/{rollback_id}/rollback",
            headers=admin,
        )
        assert rollback.status_code == 200

    assert notification.call_count == 5
    memory.assert_called_once()
    assert memory.call_args.args[2] == "FIRST_COOK"
    expected = [
        (("order_status_changed", completed_id),),
        (("order_status_changed", completed_id),),
        (("order_status_changed", completed_id),),
        (("order_status_changed", rollback_id),),
        (("order_status_changed", rollback_id),),
        (("order_status_changed", rollback_id),),
    ]
    assert [call.args for call in broadcast.await_args_list] == [
        item[0] for item in expected
    ]


def test_non_game_stats_match_the_pre_migration_query_semantics():
    """Stats services retain counts, grouping, sort order and ten-row recency."""
    marker = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        dish = _dish(db, marker)
        first = order_service.create_order(db, _order_data(dish.id, f"gf_stats_a_{marker}"))
        second = order_service.create_order(db, _order_data(dish.id, f"gf_stats_b_{marker}"))
        _complete(db, first.id)

        expected_summary = {
            "total_orders": db.query(func.count(models.Order.id)).scalar() or 0,
            "completed_orders": db.query(func.count(models.Order.id))
            .filter(models.Order.status == "已完成")
            .scalar()
            or 0,
            "last_order_at": db.query(func.max(models.Order.created_at)).scalar(),
        }
        assert stats_service.get_stats_summary(db) == expected_summary

        dish_rows = stats_service.get_dish_stats(db)
        matching = [row for row in dish_rows if row["dish_id"] == dish.id]
        assert matching[0]["dish_name"] == dish.name
        assert matching[0]["total_quantity"] == 4
        assert all(
            dish_rows[index]["total_quantity"]
            >= dish_rows[index + 1]["total_quantity"]
            for index in range(len(dish_rows) - 1)
        )
        recent = stats_service.get_recent_orders(db)
        assert len(recent) <= 10
        assert recent == sorted(recent, key=lambda item: item.created_at, reverse=True)
        assert second.id in {item.id for item in recent}
