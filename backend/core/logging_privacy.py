"""Low-cardinality logging helpers that never expose business identifiers."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Any


_PROCESS_LOG_SALT = secrets.token_bytes(32)
_SAFE_KIND = re.compile(r"[^a-z0-9_-]+")


def opaque_log_reference(kind: str, value: Any) -> str:
    """Return a process-local stable reference without revealing ``value``.

    A random in-memory HMAC key prevents offline enumeration of short room
    codes. References intentionally change after restart and must never be
    persisted or used as business identifiers.
    """
    safe_kind = _SAFE_KIND.sub("-", kind.strip().lower()).strip("-")[:24] or "value"
    payload = f"{safe_kind}\0{value}".encode("utf-8", errors="replace")
    digest = hmac.new(_PROCESS_LOG_SALT, payload, hashlib.sha256).hexdigest()[:12]
    return f"{safe_kind}:{digest}"


def route_template(scope: dict[str, Any]) -> str:
    """Return the matched framework route or a constant unmatched marker."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path.startswith("/"):
        return path
    return "/unmatched"


__all__ = ["opaque_log_reference", "route_template"]
