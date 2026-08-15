"""Create and clean isolated SQLite targets before application imports.

This module is intentionally test-only.  It configures the existing production
``database.py`` boundary; it does not construct another engine, ``Base`` or
``SessionLocal``.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from typing import Final
import uuid


BACKEND_DIR: Final = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final = BACKEND_DIR.parent
DEFAULT_DEVELOPMENT_DATABASE: Final = BACKEND_DIR / "girlfriend_menu.db"
DEFAULT_TEST_DATABASE_ROOT: Final = BACKEND_DIR / ".test-tmp"
_TEST_DATABASE_PREFIX: Final = "loveos-test-"
_OWNED_DATABASES: dict[str, Path] = {}


class DatabaseIsolationError(RuntimeError):
    """Base error for an unsafe test/diagnostic database lifecycle."""


class DatabaseIsolationOrderError(DatabaseIsolationError):
    """Report that application settings or the engine were initialized too soon."""


class UnsafeDatabasePathError(DatabaseIsolationError, ValueError):
    """Reject a path that cannot be proven safe for test-only cleanup."""


@dataclass(frozen=True)
class FileFingerprint:
    """Read-only metadata used to prove a database artifact did not change."""

    exists: bool
    size: int | None = None
    mtime_ns: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class DatabaseFileSnapshot:
    """Fingerprint the SQLite file and its two possible journal sidecars."""

    database: FileFingerprint
    wal: FileFingerprint
    shm: FileFingerprint


@dataclass(frozen=True)
class IsolatedDatabase:
    """Opaque ownership proof for one helper-generated or claimed test database."""

    path: Path
    url: str
    _ownership_token: str = field(repr=False)

    def activate(
        self,
        environ: MutableMapping[str, str] | None = None,
    ) -> None:
        """Set test configuration before ``database`` can bind its global engine."""
        activate_isolated_database(self, environ=environ)

    def cleanup(self) -> None:
        """Delete only this helper-owned SQLite file and its exact sidecars."""
        cleanup_isolated_database(self)


def _path_from_input(value: os.PathLike[str] | str, *, label: str) -> Path:
    raw = os.fspath(value)
    if "://" in raw:
        raise UnsafeDatabasePathError(f"{label} must be a local SQLite path, not a URL")
    requested = Path(raw)
    if requested in {Path("."), Path("..")}:
        raise UnsafeDatabasePathError(f"{label} cannot be '.' or '..'")
    return requested.resolve(strict=False)


def _forbidden_directories() -> set[Path]:
    return {
        BACKEND_DIR.resolve(),
        PROJECT_ROOT.resolve(),
        Path.cwd().resolve(),
        Path.home().resolve(),
        Path(tempfile.gettempdir()).resolve(),
    }


def _validate_root(root: os.PathLike[str] | str) -> Path:
    resolved = _path_from_input(root, label="test database root")
    if resolved in _forbidden_directories():
        raise UnsafeDatabasePathError(
            f"refusing dangerous test database root: {resolved}"
        )
    if resolved == DEFAULT_DEVELOPMENT_DATABASE.resolve():
        raise UnsafeDatabasePathError("default development database is never a test root")
    if resolved.exists() and not resolved.is_dir():
        raise UnsafeDatabasePathError(f"test database root is not a directory: {resolved}")
    return resolved


def _validate_database_path(path: os.PathLike[str] | str) -> Path:
    resolved = _path_from_input(path, label="test database path")
    if resolved in _forbidden_directories():
        raise UnsafeDatabasePathError(f"refusing dangerous cleanup target: {resolved}")
    if resolved == DEFAULT_DEVELOPMENT_DATABASE.resolve():
        raise UnsafeDatabasePathError("default development database is never a test target")
    if resolved.parent in _forbidden_directories():
        raise UnsafeDatabasePathError(
            f"test database cannot be created directly in protected root: {resolved.parent}"
        )
    if resolved.suffix.lower() != ".db":
        raise UnsafeDatabasePathError("isolated SQLite path must use a .db suffix")
    return resolved


def create_isolated_database(
    *,
    root: os.PathLike[str] | str | None = None,
    database_path: os.PathLike[str] | str | None = None,
) -> IsolatedDatabase:
    """Claim one absent SQLite path and return its non-forgeable cleanup handle."""
    if root is not None and database_path is not None:
        raise UnsafeDatabasePathError("provide either root or database_path, not both")

    if database_path is None:
        safe_root = _validate_root(root or DEFAULT_TEST_DATABASE_ROOT)
        safe_root.mkdir(parents=True, exist_ok=True)
        path = safe_root / f"{_TEST_DATABASE_PREFIX}{uuid.uuid4().hex}.db"
    else:
        path = _validate_database_path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    path = _validate_database_path(path)
    if path.exists():
        raise UnsafeDatabasePathError(
            f"refusing to claim pre-existing database as test-owned: {path}"
        )

    token = uuid.uuid4().hex
    _OWNED_DATABASES[token] = path
    return IsolatedDatabase(
        path=path,
        url=f"sqlite:///{path.as_posix()}",
        _ownership_token=token,
    )


def activate_isolated_database(
    isolation: IsolatedDatabase,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Activate an owned SQLite URL, refusing late application initialization."""
    owned_path = _OWNED_DATABASES.get(isolation._ownership_token)
    if owned_path != isolation.path:
        raise UnsafeDatabasePathError("test database ownership proof is invalid")
    if "database" in sys.modules:
        raise DatabaseIsolationOrderError(
            "database was imported before test isolation; activate the bootstrap first"
        )

    settings_module = sys.modules.get("core.settings")
    if settings_module is not None:
        get_settings = getattr(settings_module, "get_settings", None)
        if get_settings is not None and get_settings.cache_info().currsize:
            raise DatabaseIsolationOrderError(
                "application settings were cached before test database isolation"
            )

    target_environment = environ if environ is not None else os.environ
    target_environment["DATABASE_URL"] = isolation.url
    target_environment["APP_ENV"] = "test"


def cleanup_isolated_database(isolation: IsolatedDatabase) -> None:
    """Remove only artifacts associated with a live helper ownership token."""
    if not isinstance(isolation, IsolatedDatabase):
        raise UnsafeDatabasePathError(
            "cleanup requires an IsolatedDatabase ownership handle"
        )
    owned_path = _OWNED_DATABASES.get(isolation._ownership_token)
    if owned_path != isolation.path:
        raise UnsafeDatabasePathError("refusing cleanup without active ownership proof")
    safe_path = _validate_database_path(owned_path)

    for artifact in (
        safe_path,
        Path(f"{safe_path}-wal"),
        Path(f"{safe_path}-shm"),
    ):
        if artifact.exists():
            if not artifact.is_file():
                raise UnsafeDatabasePathError(
                    f"refusing to delete non-file database artifact: {artifact}"
                )
            artifact.unlink()
    _OWNED_DATABASES.pop(isolation._ownership_token)


def _fingerprint(path: Path) -> FileFingerprint:
    if not path.exists():
        return FileFingerprint(exists=False)
    if not path.is_file():
        raise UnsafeDatabasePathError(f"database snapshot target is not a file: {path}")
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return FileFingerprint(
        exists=True,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=digest.hexdigest(),
    )


def snapshot_database_file(path: os.PathLike[str] | str) -> DatabaseFileSnapshot:
    """Read metadata and hashes without opening SQLite or mutating its journals."""
    resolved = _path_from_input(path, label="database snapshot path")
    return DatabaseFileSnapshot(
        database=_fingerprint(resolved),
        wal=_fingerprint(Path(f"{resolved}-wal")),
        shm=_fingerprint(Path(f"{resolved}-shm")),
    )
