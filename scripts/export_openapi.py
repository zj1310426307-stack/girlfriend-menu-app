"""Render the FastAPI OpenAPI document as a deterministic V3 contract artifact."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
TARGET = ROOT / "docs" / "v3-migration" / "openapi-v3.json"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from main import app  # noqa: E402


def render_openapi() -> str:
    """Return the application-owned OpenAPI 3.1 contract with stable ordering."""
    return json.dumps(
        app.openapi(),
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"


def main() -> int:
    """Print, write, or check the deterministic contract artifact."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rendered = render_openapi()
    if args.write:
        TARGET.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"wrote {TARGET.relative_to(ROOT)}")
        return 0
    if not args.check:
        sys.stdout.write(rendered)
        return 0
    if not TARGET.exists():
        print(f"missing OpenAPI snapshot: {TARGET}", file=sys.stderr)
        return 1
    current = TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")
    if current != rendered:
        print("docs/v3-migration/openapi-v3.json is out of date", file=sys.stderr)
        return 1
    print("docs/v3-migration/openapi-v3.json is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
