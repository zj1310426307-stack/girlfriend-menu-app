"""Every V2 HTTP and WebSocket path must survive the additive V3 migration."""

from pathlib import Path
import re

from fastapi.routing import APIRoute, APIWebSocketRoute

from main import app


INVENTORY = Path(__file__).parents[2] / "docs" / "v3-migration" / "api-inventory.md"
HTTP_LINE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)$", re.MULTILINE)
WS_LINE = re.compile(r"^WS\s+(/\S+)$", re.MULTILINE)


def _current_http_routes() -> set[tuple[str, str]]:
    """Read method/path pairs from FastAPI rather than source formatting."""
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }


def _current_websockets() -> set[str]:
    """Read WebSocket paths from the assembled application."""
    return {
        route.path for route in app.routes if isinstance(route, APIWebSocketRoute)
    }


def test_all_documented_v2_http_routes_remain_available() -> None:
    """Treat the audited 89 business method/path pairs as an immutable subset."""
    source = INVENTORY.read_text(encoding="utf-8")
    baseline = set(HTTP_LINE.findall(source))
    assert len(baseline) == 89
    current = _current_http_routes()
    assert baseline <= current
    assert ("GET", "/api/bootstrap") in current
    assert ("POST", "/api/customers/wechat-session") in current
    assert len({route for route in current if route[1].startswith("/api/")}) == 90


def test_all_documented_v2_websockets_remain_available() -> None:
    """Preserve all deployed socket paths while internals migrate to plugins."""
    source = INVENTORY.read_text(encoding="utf-8")
    baseline = set(WS_LINE.findall(source))
    assert len(baseline) == 3
    assert baseline == _current_websockets()


def test_openapi_exposes_the_v3_version_and_bootstrap_contract() -> None:
    """Keep generated clients synchronized with the assembled FastAPI app."""
    schema = app.openapi()
    assert schema["openapi"].startswith("3.1")
    assert schema["info"]["version"] == "3.0.0"
    assert "get" in schema["paths"]["/api/bootstrap"]
