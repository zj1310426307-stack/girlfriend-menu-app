"""Database-owned administrator hash and append-only authentication audit."""

from __future__ import annotations

from fastapi.testclient import TestClient

from auth import hash_password, verify_password
from database import SessionLocal
from test_api import app
import models


def test_admin_login_uses_database_hash_and_records_outcomes():
    """Never persist submitted credentials while retaining compatible login fields."""
    with TestClient(app) as client:
        success = client.post(
            "/api/admin/login",
            json={"password": "test-password", "invite_code": "test-invite"},
        )
        assert success.status_code == 200
        failed = client.post(
            "/api/admin/login",
            json={"password": "not-the-password", "invite_code": "test-invite"},
        )
        assert failed.status_code == 401

    with SessionLocal() as db:
        account = db.query(models.AdminAccount).filter_by(username="admin").one()
        assert account.password_hash != "test-password"
        assert "test-password" not in account.password_hash
        assert verify_password("test-password", account.password_hash)
        outcomes = [
            row.outcome
            for row in db.query(models.AdminAuthEvent)
            .filter_by(username="admin")
            .order_by(models.AdminAuthEvent.id)
        ]
        assert "SUCCESS" in outcomes
        assert outcomes[-1] == "PASSWORD_FAILED"


def test_admin_auth_event_schema_cannot_store_submitted_secrets():
    """Keep the audit shape deliberately free of password, invite, token, and IP data."""
    columns = set(models.AdminAuthEvent.__table__.columns.keys())
    assert columns == {"id", "admin_id", "username", "outcome", "created_at"}
    assert set(models.AdminAccount.__table__.columns.keys()) == {
        "id",
        "username",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
        "last_login_at",
    }


def test_server_side_bootstrap_hash_can_rotate_and_restore_database_password(monkeypatch):
    """Allow a controlled credential rotation without a password-bearing DB update."""
    rotated_password = "rotated-test-password"
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(rotated_password))
    with TestClient(app) as client:
        rotated = client.post(
            "/api/admin/login",
            json={"password": rotated_password, "invite_code": "test-invite"},
        )
        assert rotated.status_code == 200
        # Restore the suite's configured compatibility password before leaving.
        monkeypatch.delenv("ADMIN_PASSWORD_HASH")
        restored = client.post(
            "/api/admin/login",
            json={"password": "test-password", "invite_code": "test-invite"},
        )
        assert restored.status_code == 200

    with SessionLocal() as db:
        account = db.query(models.AdminAccount).filter_by(username="admin").one()
        assert verify_password("test-password", account.password_hash)
        assert db.query(models.AdminAuthEvent).filter_by(
            outcome="SUCCESS_CONFIG_ROTATION",
        ).count() >= 2


def test_config_rotation_is_not_persisted_when_invite_fails(monkeypatch):
    """Require every login factor before changing the database verifier."""
    with TestClient(app) as client:
        seeded = client.post(
            "/api/admin/login",
            json={"password": "test-password", "invite_code": "test-invite"},
        )
        assert seeded.status_code == 200

    with SessionLocal() as db:
        original_hash = (
            db.query(models.AdminAccount)
            .filter_by(username="admin")
            .one()
            .password_hash
        )

    rotated_password = "must-not-rotate-without-invite"
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(rotated_password))
    with TestClient(app) as client:
        rejected = client.post(
            "/api/admin/login",
            json={"password": rotated_password, "invite_code": "wrong-invite"},
        )
        assert rejected.status_code == 401

    with SessionLocal() as db:
        account = db.query(models.AdminAccount).filter_by(username="admin").one()
        assert account.password_hash == original_hash
        assert not verify_password(rotated_password, account.password_hash)
        assert db.query(models.AdminAuthEvent).filter_by(
            outcome="INVITE_FAILED",
        ).count() >= 1
