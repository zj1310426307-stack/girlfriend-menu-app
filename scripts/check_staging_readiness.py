"""Fail-closed, read-only readiness gate for an isolated hosted staging service."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
MAX_RESPONSE_BYTES = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 20.0


class StagingReadinessError(RuntimeError):
    """Report one safe validation failure without echoing target data."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        return None


def _dotenv_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip()
    return ""


def _normalize_origin(raw_origin: str) -> str:
    value = raw_origin.strip()
    if not value:
        raise StagingReadinessError("STAGING_API_ORIGIN is required")
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise StagingReadinessError("staging origin must be a complete HTTPS origin")
    if parsed.username or parsed.password:
        raise StagingReadinessError("staging origin must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise StagingReadinessError(
            "staging origin must not contain a path, query, or fragment"
        )
    try:
        port = parsed.port
    except ValueError as error:
        raise StagingReadinessError("staging origin has an invalid port") from error
    if port not in {None, 443}:
        raise StagingReadinessError("hosted staging origin must use the HTTPS default port")
    hostname = parsed.hostname.lower().rstrip(".")
    if "." not in hostname or hostname.endswith((".local", ".internal")):
        raise StagingReadinessError("hosted staging origin must use a public DNS name")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise StagingReadinessError("hosted staging origin must not use a direct IP address")
    return f"https://{hostname}"


def validate_staging_origin(raw_origin: str, production_origin: str) -> str:
    """Return a normalized staging origin after rejecting production reuse."""
    staging = _normalize_origin(raw_origin)
    if not production_origin.strip():
        raise StagingReadinessError("production origin guard is unavailable")
    if staging == _normalize_origin(production_origin):
        raise StagingReadinessError("staging origin must not reuse the production API")
    return staging


def _safe_target_ref(origin: str) -> str:
    return hashlib.sha256(origin.encode("utf-8")).hexdigest()[:12]


def _request_json(url: str, *, timeout: float, label: str) -> object:
    opener = build_opener(_RejectRedirects())
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "loveos-staging-gate/1"},
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise StagingReadinessError(f"{label} returned HTTP {response.status}")
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise StagingReadinessError(f"{label} returned HTTP {error.code}") from error
    except (TimeoutError, URLError):
        raise StagingReadinessError(f"{label} request failed") from None
    if len(raw_body) > MAX_RESPONSE_BYTES:
        raise StagingReadinessError(f"{label} response exceeded the size limit")
    try:
        return json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StagingReadinessError(f"{label} did not return valid JSON") from None


def validate_health(payload: object) -> None:
    if not isinstance(payload, dict):
        raise StagingReadinessError("health payload must be an object")
    if payload.get("status") != "ok" or payload.get("service") != "girlfriend-menu-api":
        raise StagingReadinessError("health payload does not identify a healthy LoveOS API")


def _validate_component(
    payload: dict[str, object], name: str, allowed_statuses: set[str]
) -> str:
    component = payload.get(name)
    if not isinstance(component, dict):
        raise StagingReadinessError(f"readiness component {name} is missing")
    status = component.get("status")
    missing = component.get("missing")
    if status not in allowed_statuses or missing != []:
        raise StagingReadinessError(f"readiness component {name} is not ready")
    return str(status)


def validate_readiness(payload: object, *, require_wechat: bool) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise StagingReadinessError("readiness payload must be an object")
    if payload.get("status") != "ready":
        raise StagingReadinessError("staging service is release-blocked")
    if payload.get("database") != "postgresql":
        raise StagingReadinessError("staging database must be PostgreSQL")
    redis_status = payload.get("redis")
    if redis_status not in {"ready", "optional-disabled"}:
        raise StagingReadinessError("readiness component redis is invalid")
    storage_status = _validate_component(payload, "storage", {"ready"})
    storage = payload["storage"]
    if not isinstance(storage, dict) or storage.get("provider") not in {"database", "s3"}:
        raise StagingReadinessError("staging storage must use a durable provider")
    authentication_status = _validate_component(payload, "authentication", {"ready"})
    allowed_wechat = {"ready"} if require_wechat else {"ready", "optional-disabled"}
    wechat_status = _validate_component(payload, "wechat_login", allowed_wechat)
    return {
        "database": "postgresql",
        "redis": str(redis_status),
        "storage": storage_status,
        "authentication": authentication_status,
        "wechat_login": wechat_status,
    }


def run_checks(
    origin: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    require_wechat: bool = False,
    fetch_json: Callable[..., object] = _request_json,
) -> dict[str, str]:
    health = fetch_json(f"{origin}/api/health", timeout=timeout, label="health")
    validate_health(health)
    readiness = fetch_json(f"{origin}/api/ready", timeout=timeout, label="readiness")
    return validate_readiness(readiness, require_wechat=require_wechat)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify an isolated staging API without creating business data."
    )
    parser.add_argument(
        "--require-wechat",
        action="store_true",
        help="Require the WeChat integration to be enabled and ready.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-request timeout in seconds (default: 20).",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.timeout <= 0 or args.timeout > 60:
        print("staging readiness failed: timeout must be between 0 and 60 seconds")
        return 2
    production_origin = _dotenv_value(
        ROOT / "miniprogram" / ".env.production", "TARO_APP_API_ORIGIN"
    )
    try:
        origin = validate_staging_origin(
            os.getenv("STAGING_API_ORIGIN", ""), production_origin
        )
        summary = run_checks(
            origin,
            timeout=args.timeout,
            require_wechat=args.require_wechat,
        )
    except StagingReadinessError as error:
        print(f"staging readiness failed: {error}")
        return 1
    fields = " ".join(f"{name}={value}" for name, value in summary.items())
    print(f"staging readiness passed target_ref={_safe_target_ref(origin)} {fields}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
