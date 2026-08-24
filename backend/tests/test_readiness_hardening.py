"""Authentication readiness contracts for safe release decisions."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from api.routes import system as system_routes
from auth import hash_password
from core.settings import reset_settings_cache
from services import readiness_service
from test_api import app


def _complete_auth_config(monkeypatch, *, app_env: str = "test") -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-password")
    monkeypatch.setenv("ADMIN_INVITE_CODE", "admin-invite")
    monkeypatch.setenv("CUSTOMER_INVITE_CODE", "customer-invite")
    monkeypatch.setenv("ADMIN_SECRET", "runtime-secret-with-enough-entropy")
    reset_settings_cache()


def _database_admin(*, active: bool = True):
    return SimpleNamespace(
        is_active=active,
        password_hash=hash_password("database-password", salt=b"0" * 16),
    )


def test_no_admin_account_requires_bootstrap_credential(monkeypatch):
    _complete_auth_config(monkeypatch)
    monkeypatch.delenv("ADMIN_PASSWORD")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.setattr(readiness_service, "_load_admin_account", lambda db: None)

    result = readiness_service.authentication_readiness(object())

    assert result == {
        "status": "release-blocked",
        "missing": ["ADMIN_PASSWORD_OR_HASH"],
    }


def test_active_database_admin_does_not_require_bootstrap_password(monkeypatch):
    _complete_auth_config(monkeypatch)
    monkeypatch.delenv("ADMIN_PASSWORD")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.setattr(
        readiness_service,
        "_load_admin_account",
        lambda db: _database_admin(),
    )

    assert readiness_service.authentication_readiness(object()) == {
        "status": "ready",
        "missing": [],
    }


def test_disabled_database_admin_blocks_release(monkeypatch):
    _complete_auth_config(monkeypatch)
    monkeypatch.setattr(
        readiness_service,
        "_load_admin_account",
        lambda db: _database_admin(active=False),
    )

    assert readiness_service.authentication_readiness(object()) == {
        "status": "release-blocked",
        "missing": ["ADMIN_ACCOUNT_ACTIVE"],
    }


def test_managed_environment_requires_separate_invites(monkeypatch):
    _complete_auth_config(monkeypatch, app_env="staging")
    monkeypatch.setenv("CUSTOMER_INVITE_CODE", "shared-invite")
    monkeypatch.setenv("ADMIN_INVITE_CODE", "shared-invite")
    monkeypatch.setattr(
        readiness_service,
        "_load_admin_account",
        lambda db: _database_admin(),
    )

    result = readiness_service.authentication_readiness(object())

    assert result == {
        "status": "release-blocked",
        "missing": ["AUTH_INVITE_SEPARATION"],
    }
    assert "shared-invite" not in repr(result)


def test_readiness_lists_only_safe_missing_names(monkeypatch):
    secret_values = {
        "ADMIN_PASSWORD": "password-private-sentinel",
        "ADMIN_INVITE_CODE": "admin-private-sentinel",
        "CUSTOMER_INVITE_CODE": "customer-private-sentinel",
        "ADMIN_SECRET": "short-private-sentinel",
    }
    for name, value in secret_values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(readiness_service, "_load_admin_account", lambda db: None)

    result = readiness_service.authentication_readiness(object())
    rendered = repr(result)

    assert result["status"] == "ready"
    assert all(value not in rendered for value in secret_values.values())


def test_readiness_reports_all_missing_auth_configuration(monkeypatch):
    for name in (
        "ADMIN_PASSWORD",
        "ADMIN_PASSWORD_HASH",
        "ADMIN_INVITE_CODE",
        "CUSTOMER_INVITE_CODE",
        "ADMIN_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(readiness_service, "_load_admin_account", lambda db: None)

    assert readiness_service.authentication_readiness(object()) == {
        "status": "release-blocked",
        "missing": [
            "ADMIN_INVITE_CODE",
            "ADMIN_PASSWORD_OR_HASH",
            "ADMIN_SECRET",
            "CUSTOMER_INVITE_CODE",
        ],
    }


def test_admin_store_failure_is_a_safe_release_blocker(monkeypatch):
    _complete_auth_config(monkeypatch)

    def fail_to_load(db):
        del db
        raise SQLAlchemyError("database-private-sentinel")

    monkeypatch.setattr(readiness_service, "_load_admin_account", fail_to_load)

    result = readiness_service.authentication_readiness(object())

    assert result == {
        "status": "release-blocked",
        "missing": ["ADMIN_ACCOUNT_STORE"],
    }
    assert "database-private-sentinel" not in repr(result)


def test_invalid_database_password_hash_blocks_release(monkeypatch):
    _complete_auth_config(monkeypatch)
    monkeypatch.setattr(
        readiness_service,
        "_load_admin_account",
        lambda db: SimpleNamespace(is_active=True, password_hash="not-a-valid-hash"),
    )

    assert readiness_service.authentication_readiness(object()) == {
        "status": "release-blocked",
        "missing": ["ADMIN_ACCOUNT_PASSWORD_HASH"],
    }


def test_invalid_bootstrap_hash_takes_precedence_over_plain_password(monkeypatch):
    _complete_auth_config(monkeypatch)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "not-a-valid-hash")
    monkeypatch.setattr(readiness_service, "_load_admin_account", lambda db: None)

    assert readiness_service.authentication_readiness(object()) == {
        "status": "release-blocked",
        "missing": ["ADMIN_PASSWORD_HASH"],
    }


def test_top_level_readiness_aggregates_authentication_blocker(monkeypatch):
    monkeypatch.setattr(
        system_routes,
        "authentication_readiness",
        lambda db: {"status": "release-blocked", "missing": ["ADMIN_SECRET"]},
    )

    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "release-blocked"
    assert response.json()["authentication"] == {
        "status": "release-blocked",
        "missing": ["ADMIN_SECRET"],
    }
