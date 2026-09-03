"""Create a read-only logical backup of the currently deployed legacy API.

This is the fallback used when PostgreSQL client tools are unavailable locally.
It exports every resource exposed by the pre-V2.9 production API before the
database migrations run.  Legacy admin order responses already embed their
optional review, so the exporter must not call the customer-owned review
detail endpoint with an admin token.  The admin password and token are never
written to disk or printed.
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


def required_configuration() -> tuple[str, str, str]:
    """Load every production target and credential explicitly before networking."""
    values = {
        "PRODUCTION_API_ORIGIN": os.getenv("PRODUCTION_API_ORIGIN", "").strip(),
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD", ""),
        "ADMIN_INVITE_CODE": os.getenv("ADMIN_INVITE_CODE", ""),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SystemExit(
            "Production API backup requires explicit environment variables: "
            + ", ".join(missing)
        )
    api_origin = values["PRODUCTION_API_ORIGIN"].rstrip("/")
    if not api_origin.startswith("https://"):
        raise SystemExit("PRODUCTION_API_ORIGIN must use HTTPS")
    return api_origin, values["ADMIN_PASSWORD"], values["ADMIN_INVITE_CODE"]


def request_json(
    api_origin: str,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str | None = None,
):
    """Send one authenticated or public request to the validated explicit origin."""
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{api_origin}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    """Validate configuration first, then export the legacy production resources."""
    api_origin, admin_password, admin_invite_code = required_configuration()

    login = request_json(
        api_origin,
        "/api/admin/login",
        method="POST",
        body={"password": admin_password, "invite_code": admin_invite_code},
    )
    token = login.get("token")
    if not token:
        raise SystemExit("Admin login did not return a token")

    orders = request_json(api_origin, "/api/orders", token=token)
    reviews = {str(order["id"]): order.get("review") for order in orders}
    payload = {
        "format": "girlfriend-menu-api-logical-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": api_origin,
        "health": request_json(api_origin, "/api/health"),
        "dishes": request_json(api_origin, "/api/dishes"),
        "orders": orders,
        "reviews": reviews,
        "stats": {
            "summary": request_json(api_origin, "/api/stats/summary", token=token),
            "dishes": request_json(api_origin, "/api/stats/dishes", token=token),
            "recent": request_json(api_origin, "/api/stats/recent", token=token),
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
