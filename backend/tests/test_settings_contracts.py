"""Compatibility contracts for the Phase 3.0 settings facade and old boundaries."""

from pathlib import Path

import pytest
from fastapi import HTTPException

import api.dependencies as api_dependencies
import auth
import core.settings as settings_module
import customer_service
import database
import main as app_main
import storage
from core import game_room_lease
from core.settings import BACKEND_DIR, get_settings, load_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def ignore_developer_dotenv(monkeypatch, tmp_path):
    """Keep contracts deterministic even when a developer has a private backend/.env."""
    monkeypatch.setattr(settings_module, "ENV_FILE", tmp_path / "missing.env")
    reset_settings_cache()


def _reload_settings(monkeypatch, **values):
    """Apply an environment matrix row and reload the one supported cache."""
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    reset_settings_cache()
    return get_settings()


def test_default_sqlite_url_uses_absolute_backend_database(monkeypatch):
    """Keep the old absolute backend/girlfriend_menu.db fallback."""
    _reload_settings(monkeypatch, DATABASE_URL=None)
    expected = f"sqlite:///{BACKEND_DIR / 'girlfriend_menu.db'}"
    assert database.configured_database_url() == expected
    assert database.database_engine_options(expected)["connect_args"] == {
        "check_same_thread": False,
    }


def test_postgres_scheme_normalization_is_unchanged(monkeypatch):
    """Keep Render-style postgres:// URLs compatible with SQLAlchemy."""
    _reload_settings(
        monkeypatch,
        DATABASE_URL="postgres://user:password@db.example/app",
    )
    assert database.configured_database_url() == (
        "postgresql://user:password@db.example/app"
    )


def test_database_pool_bounds_are_applied_at_engine_boundary(monkeypatch):
    """Keep all four existing pool lower bounds for non-SQLite engines."""
    _reload_settings(
        monkeypatch,
        DB_POOL_SIZE="0",
        DB_MAX_OVERFLOW="-2",
        DB_POOL_TIMEOUT="1",
        DB_POOL_RECYCLE="10",
    )
    options = database.database_engine_options("postgresql://db.example/app")
    assert options == {
        "pool_pre_ping": True,
        "pool_size": 1,
        "max_overflow": 0,
        "pool_timeout": 5,
        "pool_recycle": 300,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("30", 30), ("0", 1), ("999", 365), ("invalid", 90)],
)
def test_customer_session_ttl_preserves_fallback_and_bounds(monkeypatch, raw, expected):
    """Keep invalid input fallback and the previous 1..365 day range."""
    _reload_settings(monkeypatch, CUSTOMER_SESSION_TTL_DAYS=raw)
    assert customer_service._session_ttl().days == expected


@pytest.mark.parametrize(("raw", "expected"), [("3", 15), ("45", 45)])
def test_game_room_lease_preserves_minimum(monkeypatch, raw, expected):
    """Keep the lease's existing fifteen-second lower bound."""
    _reload_settings(monkeypatch, GAME_ROOM_LEASE_SECONDS=raw)
    assert game_room_lease.configured_lease_seconds() == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("true", True), ("YES", True), ("false", False), (" true ", False)],
)
def test_legacy_header_boolean_parser_is_unchanged(monkeypatch, raw, expected):
    """Accept only the exact old true set after lower-casing."""
    _reload_settings(monkeypatch, ALLOW_LEGACY_CUSTOMER_HEADER=raw)
    assert api_dependencies.allow_legacy_customer_header() is expected


def test_local_storage_remains_available_in_development(monkeypatch):
    """Keep local uploads usable outside production."""
    _reload_settings(monkeypatch, APP_ENV="development", UPLOAD_PROVIDER="local")
    assert isinstance(storage.get_storage_provider(), storage.LocalStorageProvider)
    assert storage.storage_readiness() == {
        "provider": "local",
        "status": "ready",
        "missing": [],
    }


def test_production_local_storage_remains_release_blocked(monkeypatch):
    """Keep the release readiness signal without turning it into startup failure."""
    _reload_settings(monkeypatch, APP_ENV="production", UPLOAD_PROVIDER="local")
    assert isinstance(storage.get_storage_provider(), storage.LocalStorageProvider)
    assert storage.storage_readiness()["status"] == "release-blocked"


def test_s3_missing_configuration_behavior_is_unchanged(monkeypatch):
    """Report every required S3 field and fail only when the provider is constructed."""
    values = {
        "UPLOAD_PROVIDER": "s3",
        "S3_BUCKET": None,
        "S3_ACCESS_KEY_ID": None,
        "S3_SECRET_ACCESS_KEY": None,
        "S3_PUBLIC_BASE_URL": None,
    }
    _reload_settings(monkeypatch, **values)
    readiness = storage.storage_readiness()
    assert readiness["status"] == "release-blocked"
    assert readiness["missing"] == list(storage.S3_REQUIRED_ENV)
    with pytest.raises(ValueError, match="对象存储缺少配置"):
        storage.S3CompatibleStorageProvider()


def test_admin_secret_remains_required_on_use(monkeypatch):
    """Allow Settings/app construction without a secret, then fail at token use."""
    settings = _reload_settings(monkeypatch, ADMIN_SECRET=None)
    assert settings.admin_secret is None
    with pytest.raises(RuntimeError, match="ADMIN_SECRET must contain at least 16 characters"):
        auth._admin_secret()


def test_secrets_are_redacted_from_repr_and_failure(monkeypatch):
    """Prevent credentials and invite codes from appearing in model text or exceptions."""
    secrets = {
        "ADMIN_PASSWORD": "admin-password-private",
        "ADMIN_INVITE_CODE": "admin-invite-private",
        "ADMIN_SECRET": "short-private",
        "CUSTOMER_INVITE_CODE": "customer-invite-private",
        "DATABASE_URL": "postgres://user:database-password@db.example/app",
        "S3_ACCESS_KEY_ID": "s3-access-private",
        "S3_SECRET_ACCESS_KEY": "s3-secret-private",
        "REDIS_URL": "redis://:redis-password@redis.example/0",
    }
    settings = _reload_settings(monkeypatch, **secrets)
    rendered = f"{settings!r}\n{settings!s}"
    for value in secrets.values():
        assert value not in rendered
    with pytest.raises(RuntimeError) as error:
        settings.require_admin_secret()
    assert secrets["ADMIN_SECRET"] not in str(error.value)
    assert "customer_token" not in rendered.lower()


def test_startup_setting_remains_cached_until_explicit_reset(monkeypatch):
    """Keep initialized infrastructure stable while fresh snapshots see new env."""
    first = _reload_settings(monkeypatch, DATABASE_URL="sqlite:///first.db")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///second.db")
    assert get_settings() is first
    assert database.configured_database_url() == "sqlite:///first.db"
    assert load_settings().normalized_database_url == "sqlite:///second.db"
    reset_settings_cache()
    assert database.configured_database_url() == "sqlite:///second.db"


def test_runtime_legacy_header_observes_changes_without_cache_reset(monkeypatch):
    """Preserve consecutive-request true-to-false legacy-header semantics."""
    _reload_settings(monkeypatch, ALLOW_LEGACY_CUSTOMER_HEADER="true")
    assert api_dependencies.allow_legacy_customer_header() is True
    monkeypatch.setenv("ALLOW_LEGACY_CUSTOMER_HEADER", "false")
    assert api_dependencies.allow_legacy_customer_header() is False


def test_runtime_upload_provider_observes_changes_without_cache_reset(monkeypatch):
    """Preserve provider selection when deployment configuration changes in-process."""
    _reload_settings(monkeypatch, APP_ENV="test", UPLOAD_PROVIDER="local")
    assert storage.storage_readiness()["provider"] == "local"
    monkeypatch.setenv("UPLOAD_PROVIDER", "s3")
    for name in storage.S3_REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    assert storage.storage_readiness() == {
        "provider": "s3",
        "status": "release-blocked",
        "missing": list(storage.S3_REQUIRED_ENV),
    }


def test_admin_secret_is_fresh_and_required_only_on_use(monkeypatch):
    """Observe auth secret rotation without making application startup require it."""
    _reload_settings(monkeypatch, ADMIN_SECRET="too-short")
    with pytest.raises(RuntimeError, match="ADMIN_SECRET must contain at least 16 characters"):
        auth._admin_secret()
    monkeypatch.setenv("ADMIN_SECRET", "first-runtime-secret")
    assert auth._admin_secret() == "first-runtime-secret"
    monkeypatch.setenv("ADMIN_SECRET", "second-runtime-secret")
    assert auth._admin_secret() == "second-runtime-secret"


def test_runtime_auth_and_customer_values_observe_changes(monkeypatch):
    """Keep request/session credentials and TTL observable at their old call sites."""
    _reload_settings(
        monkeypatch,
        ADMIN_PASSWORD="first-password",
        ADMIN_INVITE_CODE="first-admin-invite",
        CUSTOMER_INVITE_CODE="first-customer-invite",
        CUSTOMER_SESSION_TTL_DAYS="30",
    )
    assert api_dependencies.get_admin_password() == "first-password"
    assert api_dependencies.get_admin_invite_code() == "first-admin-invite"
    customer_service.verify_invite("first-customer-invite")
    assert customer_service._session_ttl().days == 30

    monkeypatch.setenv("ADMIN_PASSWORD", "second-password")
    monkeypatch.setenv("ADMIN_INVITE_CODE", "second-admin-invite")
    monkeypatch.setenv("CUSTOMER_INVITE_CODE", "second-customer-invite")
    monkeypatch.setenv("CUSTOMER_SESSION_TTL_DAYS", "45")
    assert api_dependencies.get_admin_password() == "second-password"
    assert api_dependencies.get_admin_invite_code() == "second-admin-invite"
    with pytest.raises(HTTPException) as old_invite:
        customer_service.verify_invite("first-customer-invite")
    assert getattr(old_invite.value, "status_code", None) == 401
    customer_service.verify_invite("second-customer-invite")
    assert customer_service._session_ttl().days == 45


def test_admin_token_version_observes_rotation_without_cache_reset(monkeypatch):
    """Invalidate old admin tokens when the runtime token version changes."""
    _reload_settings(
        monkeypatch,
        ADMIN_SECRET="runtime-secret-with-enough-entropy",
        ADMIN_TOKEN_VERSION="1",
    )
    first, _ = auth.issue_admin_token()
    assert auth.verify_admin_token_value(first) is True
    monkeypatch.setenv("ADMIN_TOKEN_VERSION", "2")
    assert auth.verify_admin_token_value(first) is False
    second, _ = auth.issue_admin_token()
    assert auth.verify_admin_token_value(second) is True


def test_frontend_origins_keep_call_time_visibility(monkeypatch):
    """Preserve the legacy helper's direct call-time parsing semantics."""
    _reload_settings(monkeypatch, FRONTEND_URL="https://first.example/")
    assert app_main.get_frontend_origins() == ["https://first.example"]
    monkeypatch.setenv("FRONTEND_URL", "https://second.example/")
    assert app_main.get_frontend_origins() == ["https://second.example"]


def test_s3_readiness_observes_runtime_credential_changes(monkeypatch):
    """Revalidate S3 credentials from one fresh snapshot on every readiness call."""
    _reload_settings(monkeypatch, UPLOAD_PROVIDER="s3")
    for name in storage.S3_REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    assert storage.storage_readiness()["status"] == "release-blocked"
    monkeypatch.setenv("S3_BUCKET", "private-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "runtime-access-key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "runtime-secret-key")
    monkeypatch.setenv("S3_PUBLIC_BASE_URL", "https://images.example")
    assert storage.storage_readiness() == {
        "provider": "s3",
        "status": "ready",
        "missing": [],
    }


def test_fresh_settings_still_redact_secrets(monkeypatch):
    """Keep SecretStr redaction identical on the uncached compatibility path."""
    secret = "fresh-loader-private-secret"
    _reload_settings(monkeypatch, ADMIN_SECRET=secret, S3_SECRET_ACCESS_KEY=secret)
    rendered = f"{load_settings()!r}\n{load_settings()!s}"
    assert secret not in rendered


def test_backend_dotenv_location_is_absolute_and_cwd_independent(monkeypatch, tmp_path):
    """Load an absolute dotenv path after moving to an unrelated working directory."""
    default_env_file = BACKEND_DIR / ".env"
    assert default_env_file.is_absolute()
    env_file = tmp_path / "backend.env"
    env_file.write_text("FRONTEND_URL=https://dotenv.example/\n", encoding="utf-8")
    unrelated_cwd = tmp_path / "unrelated"
    unrelated_cwd.mkdir()
    monkeypatch.setattr(settings_module, "ENV_FILE", env_file)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.chdir(unrelated_cwd)
    reset_settings_cache()
    assert get_settings().frontend_origins == ["https://dotenv.example"]
    assert load_settings().frontend_origins == ["https://dotenv.example"]
    assert settings_module.ENV_FILE.is_absolute()


def test_runtime_modules_do_not_construct_settings_instances_directly():
    """Keep all environment-source interaction inside the central settings module."""
    settings_path = Path(settings_module.__file__).resolve()
    offenders = []
    for path in BACKEND_DIR.rglob("*.py"):
        if path.resolve() == settings_path or "tests" in path.parts or ".venv" in path.parts:
            continue
        if "Settings(" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(BACKEND_DIR).as_posix())
    assert offenders == []
