"""Create a read-only logical backup of the currently deployed legacy API.

This is the fallback used when PostgreSQL client tools are unavailable locally.
It exports every resource exposed by the pre-V2.9 production API before the
database migrations run.  The admin password and token are never written to
disk or printed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_ORIGIN = os.getenv("PRODUCTION_API_ORIGIN", "https://girlfriend-menu-api.onrender.com").rstrip("/")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "love2026")


def request_json(path: str, *, method: str = "GET", body: object | None = None, token: str | None = None):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{API_ORIGIN}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def optional_json(path: str, token: str):
    try:
        return request_json(path, token=token)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def main() -> int:
    if not ADMIN_PASSWORD:
        raise SystemExit("ADMIN_PASSWORD must be provided through the environment")

    login = request_json(
        "/api/admin/login",
        method="POST",
        body={"password": ADMIN_PASSWORD, "invite_code": ADMIN_INVITE_CODE},
    )
    token = login.get("token")
    if not token:
        raise SystemExit("Admin login did not return a token")

    orders = request_json("/api/orders", token=token)
    reviews = {
        str(order["id"]): optional_json(f"/api/orders/{order['id']}/review", token)
        for order in orders
    }
    payload = {
        "format": "girlfriend-menu-api-logical-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": API_ORIGIN,
        "health": request_json("/api/health"),
        "dishes": request_json("/api/dishes"),
        "orders": orders,
        "reviews": reviews,
        "stats": {
            "summary": request_json("/api/stats/summary", token=token),
            "dishes": request_json("/api/stats/dishes", token=token),
            "recent": request_json("/api/stats/recent", token=token),
        },
    }

    output_dir = ROOT / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = output_dir / f"production-api-before-v2.9-{stamp}.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    backup_path.write_bytes(content)
    manifest = {
        "backup": backup_path.name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "counts": {
            "dishes": len(payload["dishes"]),
            "orders": len(orders),
            "reviews": sum(review is not None for review in reviews.values()),
        },
    }
    manifest_path = backup_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"backup": str(backup_path), **manifest["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HTTPError as error:
        print(f"Production API backup failed with HTTP {error.code}", file=sys.stderr)
        raise SystemExit(1) from error
