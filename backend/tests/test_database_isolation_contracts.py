"""Regression contracts for pytest and standalone diagnostic DB isolation."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

import database
from test_support.database_isolation import (
    BACKEND_DIR,
    DEFAULT_DEVELOPMENT_DATABASE,
    PROJECT_ROOT,
    UnsafeDatabasePathError,
    cleanup_isolated_database,
    create_isolated_database,
    snapshot_database_file,
)


def _run_python(code: str, *arguments: Path, database_url: str) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["APP_ENV"] = "test"
    return subprocess.run(
        [sys.executable, "-c", code, *(str(argument) for argument in arguments)],
        cwd=BACKEND_DIR,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def test_pytest_engine_targets_the_central_isolated_database(isolated_database_path):
    """Contract A: collection can never bind the engine to the development DB."""
    engine_path = Path(database.engine.url.database).resolve()
    assert engine_path == isolated_database_path.resolve()
    assert engine_path != DEFAULT_DEVELOPMENT_DATABASE.resolve()


def test_default_development_database_is_unchanged_during_pytest(
    default_database_snapshot,
):
    """Contract B: the pre-collection database fingerprint remains unchanged."""
    assert snapshot_database_file(DEFAULT_DEVELOPMENT_DATABASE) == (
        default_database_snapshot
    )


def test_subprocess_safe_import_binds_the_explicit_sqlite_url(tmp_path):
    """Set DATABASE_URL first, then prove a fresh process binds that exact engine."""
    target = tmp_path / "safe-import.db"
    result = _run_python(
        "from pathlib import Path; import database; "
        "print(Path(database.engine.url.database).resolve()); database.engine.dispose()",
        database_url=f"sqlite:///{target.as_posix()}",
    )
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).resolve() == target.resolve()
    assert not target.exists()


def test_subprocess_bootstrap_owns_and_cleans_a_diagnostic_database(tmp_path):
    """Use the shared bootstrap before application imports in a standalone PoC."""
    root = tmp_path / "diagnostic"
    result = _run_python(
        "from pathlib import Path; import sys; "
        "from test_support.database_isolation import create_isolated_database; "
        "isolation=create_isolated_database(root=Path(sys.argv[1])); "
        "isolation.activate(); import database; "
        "connection=database.engine.connect(); connection.close(); "
        "path=isolation.path; database.engine.dispose(); isolation.cleanup(); "
        "print(path); print(path.exists())",
        root,
        database_url="sqlite:///ambient-value-must-be-replaced.db",
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout.strip().splitlines()
    assert Path(output[0]).parent.resolve() == root.resolve()
    assert output[1] == "False"


def test_subprocess_late_bootstrap_fails_loudly_without_touching_development_db(
    tmp_path,
):
    """A diagnostic that imports database first cannot silently claim isolation."""
    before = snapshot_database_file(DEFAULT_DEVELOPMENT_DATABASE)
    root = tmp_path / "late-bootstrap"
    result = _run_python(
        "from pathlib import Path; import sys; import database; "
        "from test_support.database_isolation import ("
        "DatabaseIsolationOrderError, create_isolated_database); "
        "isolation=create_isolated_database(root=Path(sys.argv[1])); "
        "\ntry:\n isolation.activate()\n"
        "except DatabaseIsolationOrderError as error:\n print(type(error).__name__)\n"
        "else:\n raise SystemExit('late bootstrap was accepted')\n"
        "finally:\n database.engine.dispose(); isolation.cleanup()",
        root,
        database_url=f"sqlite:///{DEFAULT_DEVELOPMENT_DATABASE.as_posix()}",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "DatabaseIsolationOrderError"
    assert snapshot_database_file(DEFAULT_DEVELOPMENT_DATABASE) == before


def test_cleanup_requires_a_live_helper_ownership_handle(tmp_path):
    """Never expose an arbitrary-path deletion API."""
    unrelated = tmp_path / "girlfriend_menu.db"
    unrelated.write_bytes(b"not helper-owned")
    with pytest.raises(UnsafeDatabasePathError, match="ownership handle"):
        cleanup_isolated_database(unrelated)  # type: ignore[arg-type]
    assert unrelated.read_bytes() == b"not helper-owned"


def test_helper_removes_only_the_database_it_claimed(tmp_path):
    """Allow an absent explicit test path and remove its exact SQLite artifacts."""
    target = tmp_path / "explicit-isolated.db"
    isolation = create_isolated_database(database_path=target)
    target.write_bytes(b"database")
    Path(f"{target}-wal").write_bytes(b"wal")
    Path(f"{target}-shm").write_bytes(b"shm")
    isolation.cleanup()
    assert not target.exists()
    assert not Path(f"{target}-wal").exists()
    assert not Path(f"{target}-shm").exists()


@pytest.mark.parametrize(
    "dangerous_target",
    [
        BACKEND_DIR,
        PROJECT_ROOT,
        Path("."),
        Path(".."),
        Path.home(),
        Path(tempfile.gettempdir()),
        DEFAULT_DEVELOPMENT_DATABASE,
        "postgresql://production.example/loveos",
    ],
)
def test_helper_rejects_dangerous_or_non_sqlite_targets(dangerous_target):
    """Refuse roots, production URLs and the default development database."""
    with pytest.raises(UnsafeDatabasePathError):
        create_isolated_database(database_path=dangerous_target)


def test_helper_never_claims_a_preexisting_file(tmp_path):
    """An existing file cannot be re-labelled as helper-owned and deleted."""
    target = tmp_path / "existing.db"
    target.write_bytes(b"preserve")
    with pytest.raises(UnsafeDatabasePathError, match="pre-existing"):
        create_isolated_database(database_path=target)
    assert target.read_bytes() == b"preserve"
