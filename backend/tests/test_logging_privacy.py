"""Sentinel contracts for privacy-safe operational logs."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

import core.cache as cache_module
import core.game_state_store as game_state_store_module
import main as main_module
from core.cache import StateCache
from core.game_state_store import ResilientGameStateStore
from core.logging_privacy import opaque_log_reference
from test_api import app


SENTINEL = "ROOM_CODE_SENTINEL"
REQUEST_SENTINEL = "REQUEST_ID_SENTINEL"
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _capture_log(monkeypatch, logger, *method_names: str) -> list[str]:
    messages: list[str] = []

    def record(template: str, *values) -> None:
        messages.append(template % values)

    for method_name in method_names:
        monkeypatch.setattr(logger, method_name, record)
    return messages


def test_opaque_reference_is_stable_without_revealing_short_identifier():
    first = opaque_log_reference("room", SENTINEL)
    second = opaque_log_reference("room", SENTINEL)
    other = opaque_log_reference("room", "OTHER_ROOM_CODE")
    sanitized = opaque_log_reference("Unsafe Kind Value!", SENTINEL)

    assert first == second
    assert first != other
    assert SENTINEL not in first
    assert first.startswith("room:")
    assert sanitized.startswith("unsafe-kind-value:")


def test_http_log_uses_route_template_for_dynamic_path(monkeypatch):
    messages = _capture_log(monkeypatch, main_module.logger, "info")

    with TestClient(app) as client:
        response = client.get(
            f"/api/games/rooms/{SENTINEL}",
            headers={"X-Request-Id": REQUEST_SENTINEL},
        )

    rendered = "\n".join(messages)
    assert SENTINEL not in rendered
    assert REQUEST_SENTINEL not in rendered
    assert response.headers["X-Request-Id"] == REQUEST_SENTINEL
    assert "request_ref=request:" in rendered
    assert "route=/api/games/rooms/{room_code}" in rendered


def test_http_log_uses_constant_for_unmatched_path(monkeypatch):
    messages = _capture_log(monkeypatch, main_module.logger, "info")

    with TestClient(app) as client:
        client.get(f"/not-a-route/{SENTINEL}")

    rendered = "\n".join(messages)
    assert SENTINEL not in rendered
    assert "route=/unmatched" in rendered


class _FailingRedis:
    def setex(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError(f"write failed for {SENTINEL}")

    def get(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError(f"read failed for {SENTINEL}")


def _failing_cache(monkeypatch) -> StateCache:
    cache = object.__new__(StateCache)
    cache.url = ""
    cache.client = _FailingRedis()
    cache.last_attempt = 0.0
    monkeypatch.setattr(cache, "_connect", lambda: None)
    return cache


def test_cache_failures_hide_key_and_exception_message(monkeypatch):
    messages = _capture_log(monkeypatch, cache_module.logger, "warning")
    cache = _failing_cache(monkeypatch)

    cache.set_json(f"game:room:{SENTINEL}", {"ok": True})
    cache.client = _FailingRedis()
    assert cache.get_json(f"presence:{SENTINEL}") is None

    rendered = "\n".join(messages)
    assert SENTINEL not in rendered
    assert "key_ref=cache-key:" in rendered
    assert "error_type=RuntimeError" in rendered


class _FailingGameDatabase:
    def get(self, room_code: str):
        raise RuntimeError(f"read failed for {room_code}")

    def set(self, room_code: str, state: dict, ttl_seconds: int):
        del state, ttl_seconds
        raise RuntimeError(f"write failed for {room_code}")


def test_game_state_failures_hide_room_and_exception_message(monkeypatch):
    messages = _capture_log(
        monkeypatch,
        game_state_store_module.logger,
        "warning",
        "error",
    )
    store = ResilientGameStateStore()
    store.database = _FailingGameDatabase()

    assert store.get(SENTINEL) is None
    store.set(SENTINEL, {"phase": "waiting"})

    rendered = "\n".join(messages)
    assert SENTINEL not in rendered
    assert "room_ref=room:" in rendered
    assert "error_type=RuntimeError" in rendered


def test_privacy_sensitive_modules_do_not_emit_tracebacks_or_raw_identifiers():
    paths = (
        "main.py",
        "serve.py",
        "core/cache.py",
        "core/game_state_store.py",
        "game_maintenance.py",
        "api/routes/websocket.py",
        "services/game_socket_session_service.py",
    )
    sensitive_expressions = (
        "request.url.path",
        "room_code",
        "normalized_room_code",
        "room.room_code",
        "setup.room_code",
        "key",
    )

    for relative_path in paths:
        source = (BACKEND_DIR / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        logger_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ]
        assert all(call.func.attr != "exception" for call in logger_calls)
        for call in logger_calls:
            for argument in call.args[1:]:
                rendered = ast.unparse(argument)
                contains_sensitive = any(
                    expression in rendered for expression in sensitive_expressions
                )
                if contains_sensitive:
                    assert "opaque_log_reference" in rendered
                if "error" in rendered:
                    assert rendered == "type(error).__name__"
