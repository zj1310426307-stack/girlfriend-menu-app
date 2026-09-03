"""Generate a server-side scrypt bootstrap verifier without echoing the password."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from auth import hash_password  # noqa: E402


def main() -> int:
    """Prompt twice and print only the deployable one-way verifier."""
    first = getpass("Admin password: ")
    second = getpass("Confirm password: ")
    if not first:
        raise SystemExit("password cannot be empty")
    if first != second:
        raise SystemExit("passwords do not match")
    print(hash_password(first))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
