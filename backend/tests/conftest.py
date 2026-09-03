"""Shared pytest isolation established before any application module import."""

from pathlib import Path
import sys

from test_support.database_isolation import (
    DEFAULT_DEVELOPMENT_DATABASE,
    create_isolated_database,
    snapshot_database_file,
)


_DEFAULT_DATABASE_BEFORE = snapshot_database_file(DEFAULT_DEVELOPMENT_DATABASE)
PYTEST_DATABASE_ISOLATION = create_isolated_database()
PYTEST_DATABASE_ISOLATION.activate()

# These application imports are deliberately below the database bootstrap.
import pytest  # noqa: E402

from core.settings import reset_settings_cache  # noqa: E402
from core.telemetry import shutdown_tracing  # noqa: E402
from core.rate_limit import MemoryRateLimiter  # noqa: E402


def _assert_default_database_unchanged() -> None:
    assert snapshot_database_file(DEFAULT_DEVELOPMENT_DATABASE) == (
        _DEFAULT_DATABASE_BEFORE
    ), "pytest changed the default development SQLite database"


def pytest_collection_finish(session) -> None:
    """Stop before tests if collection bound the engine outside the owned DB."""
    del session
    database_module = sys.modules.get("database")
    if database_module is not None:
        engine_path = Path(database_module.engine.url.database).resolve()
        assert engine_path == PYTEST_DATABASE_ISOLATION.path.resolve(), (
            "pytest collection bound database.engine outside the isolated SQLite file"
        )
    _assert_default_database_unchanged()


@pytest.fixture(scope="session", autouse=True)
def isolate_database_session():
    """Own one pytest DB and prove the default development DB stayed untouched."""
    yield
    database_module = sys.modules.get("database")
    if database_module is not None:
        database_module.engine.dispose()
    PYTEST_DATABASE_ISOLATION.cleanup()
    _assert_default_database_unchanged()


@pytest.fixture(scope="session")
def isolated_database_path() -> Path:
    """Expose the centrally owned target to isolation contract tests."""
    return PYTEST_DATABASE_ISOLATION.path


@pytest.fixture(scope="session")
def default_database_snapshot():
    """Expose only the read-only pre-collection fingerprint."""
    return _DEFAULT_DATABASE_BEFORE


@pytest.fixture(autouse=True)
def isolate_settings_cache():
    """Make environment monkeypatches visible without constructing ad-hoc Settings objects."""
    shutdown_tracing()
    reset_settings_cache()
    yield
    shutdown_tracing()
    reset_settings_cache()


@pytest.fixture(autouse=True)
def isolate_in_memory_rate_limits(monkeypatch):
    """Prevent one contract test's synthetic client IP from throttling another."""
    import api.dependencies as api_dependencies
    import core.rate_limit as rate_limit_module
    import main as main_module

    limiter = MemoryRateLimiter()
    monkeypatch.setattr(rate_limit_module, "rate_limiter", limiter)
    monkeypatch.setattr(api_dependencies, "rate_limiter", limiter)
    monkeypatch.setattr(main_module, "rate_limiter", limiter)
