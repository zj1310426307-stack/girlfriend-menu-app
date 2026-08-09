"""Restore a backup into an isolated target and compare manifest row counts."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile

from sqlalchemy import create_engine, inspect, text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(url: str, tables: list[str]) -> dict[str, int]:
    engine = create_engine(url)
    try:
        existing = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            return {
                table: int(connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)
                for table in tables if table in existing
            }
    finally:
        engine.dispose()


def verify(backup: Path, target_url: str | None = None) -> None:
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if _sha256(backup) != manifest["sha256"]:
        raise SystemExit("Backup checksum mismatch")
    if manifest["database_kind"] == "sqlite":
        with tempfile.TemporaryDirectory(prefix="gf-restore-") as directory:
            restored = Path(directory) / "restored.sqlite3"
            with closing(sqlite3.connect(backup)) as source, closing(sqlite3.connect(restored)) as target:
                source.backup(target)
            with closing(sqlite3.connect(restored)) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise SystemExit("SQLite integrity check failed")
            actual = _counts(f"sqlite:///{restored.as_posix()}", list(manifest["counts"]))
    else:
        if not target_url or "restore_verify" not in target_url:
            raise SystemExit("PostgreSQL verification requires an isolated --target-url containing 'restore_verify'")
        subprocess.run(
            ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl", f"--dbname={target_url}", str(backup)],
            check=True,
        )
        actual = _counts(target_url, list(manifest["counts"]))
    if actual != manifest["counts"]:
        raise SystemExit(f"Restored row counts differ: expected={manifest['counts']} actual={actual}")
    print(json.dumps({"status": "verified", "counts": actual}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("--target-url", default=None)
    args = parser.parse_args()
    verify(args.backup.resolve(), args.target_url)
