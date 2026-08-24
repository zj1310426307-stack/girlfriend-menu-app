"""Regression coverage for database-owned customer activity throttling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlalchemy.orm import joinedload, sessionmaker

from auth import hash_token
import customer_service
from database import SessionLocal, engine
import models
from test_api import app


FIXED_NOW = datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def initialize_application_schema():
    """Use the production lifespan to initialize the suite-owned database once."""
    with TestClient(app):
        yield


def _seed_customer_session(
    *,
    last_seen_at: datetime,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    is_active: bool = True,
) -> tuple[str, str, int]:
    """Create one isolated bearer identity with explicit activity state."""
    marker = uuid.uuid4().hex
    customer_id = f"gf_activity_{marker[:16]}"
    token = f"gft_activity_{marker}{uuid.uuid4().hex}"
    token_digest = hash_token(token)
    with SessionLocal() as db:
        customer = models.Customer(
            id=customer_id,
            token_hash=token_digest,
            display_name="活跃测试",
            is_active=is_active,
            created_at=FIXED_NOW - timedelta(days=1),
            updated_at=FIXED_NOW - timedelta(days=1),
            last_seen_at=last_seen_at,
        )
        session = models.CustomerSession(
            customer=customer,
            token_hash=token_digest,
            created_at=FIXED_NOW - timedelta(days=1),
            last_seen_at=last_seen_at,
            expires_at=expires_at or FIXED_NOW + timedelta(days=1),
            revoked_at=revoked_at,
        )
        db.add(customer)
        db.add(session)
        db.commit()
        return customer_id, token, session.id


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite timestamps before exact persistence assertions."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def test_hot_session_authentication_emits_no_update_or_commit(monkeypatch):
    """A bearer inside the five-minute window must remain a read-only request."""
    monkeypatch.setattr(customer_service, "utc_now", lambda: FIXED_NOW)
    original_seen = FIXED_NOW - timedelta(minutes=1)
    customer_id, token, session_id = _seed_customer_session(last_seen_at=original_seen)
    updates: list[str] = []

    def capture_updates(_connection, _cursor, statement, _parameters, _context, _many):
        """Record only persistent UPDATE statements issued by the authentication call."""
        if statement.lstrip().upper().startswith("UPDATE"):
            updates.append(statement)

    event.listen(engine, "before_cursor_execute", capture_updates)
    try:
        with SessionLocal() as db, patch.object(db, "commit", wraps=db.commit) as commit:
            customer = customer_service.authenticate(db, token)
            assert customer.id == customer_id
            assert not db.dirty
            commit.assert_not_called()
    finally:
        event.remove(engine, "before_cursor_execute", capture_updates)

    assert updates == []
    with SessionLocal() as db:
        assert _as_utc(db.get(models.CustomerSession, session_id).last_seen_at) == original_seen
        assert _as_utc(db.get(models.Customer, customer_id).last_seen_at) == original_seen


def test_stale_session_touches_once_then_enters_the_cooldown(monkeypatch):
    """The first stale caller owns one synchronized session/customer activity write."""
    monkeypatch.setattr(customer_service, "utc_now", lambda: FIXED_NOW)
    customer_id, token, session_id = _seed_customer_session(
        last_seen_at=FIXED_NOW - timedelta(minutes=6),
    )

    with SessionLocal() as db, patch.object(db, "commit", wraps=db.commit) as commit:
        assert customer_service.authenticate(db, token).id == customer_id
        assert commit.call_count == 1

    with SessionLocal() as db, patch.object(db, "commit", wraps=db.commit) as commit:
        assert customer_service.authenticate(db, token).id == customer_id
        commit.assert_not_called()

    with SessionLocal() as db:
        assert _as_utc(db.get(models.CustomerSession, session_id).last_seen_at) == FIXED_NOW
        assert _as_utc(db.get(models.Customer, customer_id).last_seen_at) == FIXED_NOW


def test_two_stale_session_views_cannot_overwrite_the_new_window(monkeypatch):
    """A stale identity-map contender must lose the database cutoff CAS without committing."""
    monkeypatch.setattr(customer_service, "utc_now", lambda: FIXED_NOW)
    old_seen = FIXED_NOW - timedelta(minutes=8)
    customer_id, token, session_id = _seed_customer_session(last_seen_at=old_seen)
    stale_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    first = stale_session_factory()
    second = stale_session_factory()
    try:
        digest = hash_token(token)
        assert (
            first.query(models.CustomerSession)
            .filter(models.CustomerSession.token_hash == digest)
            .one()
            .last_seen_at
        )
        assert (
            second.query(models.CustomerSession)
            .filter(models.CustomerSession.token_hash == digest)
            .one()
            .last_seen_at
        )
        # End both read transactions while deliberately retaining their stale views.
        first.commit()
        second.commit()

        with patch.object(first, "commit", wraps=first.commit) as first_commit:
            assert customer_service.authenticate(first, token).id == customer_id
            assert first_commit.call_count == 1
        with patch.object(second, "commit", wraps=second.commit) as second_commit:
            assert customer_service.authenticate(second, token).id == customer_id
            second_commit.assert_not_called()
    finally:
        first.close()
        second.close()

    with SessionLocal() as db:
        assert _as_utc(db.get(models.CustomerSession, session_id).last_seen_at) == FIXED_NOW
        assert _as_utc(db.get(models.Customer, customer_id).last_seen_at) == FIXED_NOW


def test_concurrent_account_deactivation_rolls_back_the_session_touch(monkeypatch):
    """A customer disabled after the first read must fail without advancing activity."""
    monkeypatch.setattr(customer_service, "utc_now", lambda: FIXED_NOW)
    old_seen = FIXED_NOW - timedelta(minutes=8)
    customer_id, token, session_id = _seed_customer_session(last_seen_at=old_seen)
    stale_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    stale_db = stale_session_factory()
    try:
        digest = hash_token(token)
        stale_view = (
            stale_db.query(models.CustomerSession)
            .options(joinedload(models.CustomerSession.customer))
            .filter(models.CustomerSession.token_hash == digest)
            .one()
        )
        assert stale_view.customer.is_active is True
        # End the read transaction but deliberately retain the validated view.
        stale_db.commit()

        with SessionLocal() as disabling_db:
            account = disabling_db.get(models.Customer, customer_id)
            account.is_active = False
            disabling_db.commit()

        with pytest.raises(HTTPException) as rejected:
            customer_service.authenticate(stale_db, token)
        assert rejected.value.status_code == 401
    finally:
        stale_db.close()

    with SessionLocal() as db:
        assert db.get(models.Customer, customer_id).is_active is False
        assert _as_utc(db.get(models.CustomerSession, session_id).last_seen_at) == old_seen
        assert _as_utc(db.get(models.Customer, customer_id).last_seen_at) == old_seen


@pytest.mark.parametrize("invalid_state", ["revoked", "expired", "inactive"])
def test_invalid_sessions_are_checked_on_every_request(monkeypatch, invalid_state):
    """Activity throttling must not weaken revocation, expiry or account-state checks."""
    monkeypatch.setattr(customer_service, "utc_now", lambda: FIXED_NOW)
    revoked_at = FIXED_NOW - timedelta(seconds=1) if invalid_state == "revoked" else None
    expires_at = FIXED_NOW - timedelta(seconds=1) if invalid_state == "expired" else None
    customer_id, token, session_id = _seed_customer_session(
        last_seen_at=FIXED_NOW - timedelta(minutes=1),
        expires_at=expires_at,
        revoked_at=revoked_at,
        is_active=invalid_state != "inactive",
    )

    with SessionLocal() as db:
        with pytest.raises(HTTPException) as rejected:
            customer_service.authenticate(db, token)
        assert rejected.value.status_code == 401

    with SessionLocal() as db:
        session = db.get(models.CustomerSession, session_id)
        customer = db.get(models.Customer, customer_id)
        assert _as_utc(session.last_seen_at) == FIXED_NOW - timedelta(minutes=1)
        if invalid_state == "expired":
            assert _as_utc(session.revoked_at) == FIXED_NOW
        assert _as_utc(customer.last_seen_at) == FIXED_NOW - timedelta(minutes=1)


def test_update_last_seen_false_skips_even_a_stale_session(monkeypatch):
    """Latency-sensitive callers keep the established explicit no-touch contract."""
    monkeypatch.setattr(customer_service, "utc_now", lambda: FIXED_NOW)
    old_seen = FIXED_NOW - timedelta(hours=1)
    customer_id, token, session_id = _seed_customer_session(last_seen_at=old_seen)

    with SessionLocal() as db, patch.object(db, "commit", wraps=db.commit) as commit:
        assert customer_service.authenticate(db, token, update_last_seen=False).id == customer_id
        assert not db.dirty
        commit.assert_not_called()

    with SessionLocal() as db:
        assert _as_utc(db.get(models.CustomerSession, session_id).last_seen_at) == old_seen
        assert _as_utc(db.get(models.Customer, customer_id).last_seen_at) == old_seen
