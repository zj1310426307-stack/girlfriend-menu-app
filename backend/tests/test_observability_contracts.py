"""Privacy, hierarchy and compatibility contracts for the R2B1 trace core."""

from __future__ import annotations

from io import StringIO
import uuid

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

import notification_service
from api.routes import websocket as websocket_routes
from core.settings import get_settings, reset_settings_cache
from core.telemetry import (
    configure_tracing,
    force_flush_tracing,
    set_span_attribute,
    trace_span,
    tracing_enabled,
)
from database import SessionLocal
from services import game_persistence_service, game_settlement_service
from test_api import app


SENTINELS = (
    "ADMIN_SECRET_SENTINEL",
    "CUSTOMER_TOKEN_SENTINEL",
    "ROOM_CODE_SENTINEL",
    "DATABASE_PASSWORD_SENTINEL",
    "S3_SECRET_SENTINEL",
)


class FailingSpanExporter(SpanExporter):
    """Raise from export so the SDK processor's business isolation is exercised."""

    def export(self, spans):
        del spans
        raise RuntimeError("simulated exporter outage")

    def shutdown(self) -> None:
        return None


def _set_trace_flags(monkeypatch, *, console: bool = False) -> None:
    """Enable only the R2B1 trace path with deterministic test configuration."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOVEOS_TRACING_ENABLED", "true")
    monkeypatch.setenv("LOVEOS_TRACING_CONSOLE", "true" if console else "false")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "loveos-test")
    reset_settings_cache()


def _clear_trace_flags(monkeypatch) -> None:
    """Exercise the documented no-op defaults with no trace configuration."""
    for name in (
        "LOVEOS_TRACING_ENABLED",
        "LOVEOS_TRACING_CONSOLE",
        "OTEL_SDK_DISABLED",
        "OTEL_SERVICE_NAME",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_settings_cache()


def _create_room() -> str:
    """Create one durable room without pre-warming the process-local manager."""
    creator = f"gf_trace_{uuid.uuid4().hex[:10]}"
    with SessionLocal() as db:
        room = game_persistence_service.create_game_room(db, "dice", creator)
        return room.room_code


def _join_room(client: TestClient) -> tuple[str, dict]:
    """Run the deployed legacy identity bridge and return its first payload."""
    room_code = _create_room()
    with client.websocket_connect(f"/ws/game/{room_code}") as socket:
        socket.send_json(
            {
                "type": "join",
                "game": "dice",
                "data": {
                    "player_id": "CUSTOMER_TOKEN_SENTINEL",
                    "name": "ROOM_CODE_SENTINEL",
                    "invite_code": "test-invite",
                },
            }
        )
        payload = socket.receive_json()
    return room_code, payload


def _settlement_event() -> dict:
    """Create a real durable round carrying private sentinels only in business data."""
    winner = f"gf_trace_win_{uuid.uuid4().hex[:8]}"
    loser = f"gf_trace_lose_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        room = game_persistence_service.create_game_room(db, "gomoku", winner)
        game_persistence_service.join_game_room(db, room.room_code, winner)
        game_persistence_service.join_game_room(db, room.room_code, loser)
        room_code = room.room_code
    return {
        "room_code": room_code,
        "game_type": "gomoku",
        "round_number": 1,
        "players": [winner, loser],
        "winner_id": winner,
        "duration": 12,
        "result": {
            "final_state": {
                "phase": "finished",
                "private_sentinels": list(SENTINELS),
            }
        },
    }


def _span_material(spans) -> str:
    """Render only exporter-visible names, resources, attributes and events."""
    material = []
    for span in spans:
        material.append(span.name)
        material.append(repr(dict(span.attributes or {})))
        material.append(repr(dict(span.resource.attributes or {})))
        material.extend(
            f"{event.name}:{dict(event.attributes or {})}" for event in span.events
        )
    return "\n".join(material)


def test_tracing_defaults_to_noop_without_console_output(monkeypatch):
    """Keep imports and manual span hooks free when tracing was not opted into."""
    _clear_trace_flags(monkeypatch)
    output = StringIO()
    assert get_settings().tracing_enabled is False
    assert configure_tracing(console_output=output) is False
    assert tracing_enabled() is False
    with trace_span("telemetry.test", {"result": "success"}) as span:
        assert span.is_recording() is False
    assert output.getvalue() == ""


def test_standard_sdk_disabled_overrides_app_opt_in(monkeypatch):
    """Honor the official OTEL_SDK_DISABLED kill switch without SDK startup."""
    _set_trace_flags(monkeypatch)
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    reset_settings_cache()
    assert configure_tracing() is False
    assert tracing_enabled() is False


def test_default_noop_app_startup_keeps_health_and_readiness(monkeypatch):
    """Start the full lifespan without any exporter, collector or credentials."""
    _clear_trace_flags(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {
            "status": "ok",
            "service": "girlfriend-menu-api",
        }
        ready = client.get("/api/ready")
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"


def test_in_memory_exporter_keeps_parent_child_context(monkeypatch):
    """Use the SDK's maintained in-memory exporter to verify context hierarchy."""
    _set_trace_flags(monkeypatch)
    exporter = InMemorySpanExporter()
    assert configure_tracing(span_exporter=exporter) is True
    with trace_span(
        "game.websocket.join",
        {"game.type": "dice", "result": "success"},
    ) as parent:
        with trace_span(
            "game.lease.acquire",
            {"result": "acquired", "retry.count": 0},
        ):
            pass
    assert force_flush_tracing()
    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert spans["game.lease.acquire"].parent.span_id == parent.get_span_context().span_id


def test_websocket_join_snapshot_and_lease_spans_preserve_payload(monkeypatch):
    """Trace the real join tree without changing its first WebSocket envelope."""
    _set_trace_flags(monkeypatch)
    exporter = InMemorySpanExporter()
    assert configure_tracing(span_exporter=exporter)
    with TestClient(app) as client:
        room_code, payload = _join_room(client)
        assert set(payload) == {"type", "game", "room_code", "data"}
        assert payload["type"] == "state"
        assert payload["game"] == "dice"
        assert payload["room_code"] == room_code

    spans = exporter.get_finished_spans()
    by_name = {span.name: span for span in spans}
    parent = by_name["game.websocket.join"]
    assert by_name["game.lease.acquire"].parent.span_id == parent.context.span_id
    assert by_name["game.snapshot.load"].parent.span_id == parent.context.span_id
    assert by_name["game.snapshot.load"].attributes["state.source"] in {
        "postgresql",
        "redis",
        "memory",
        "none",
    }


def test_websocket_first_state_log_keeps_metrics_without_room_code(monkeypatch):
    """Keep hosted latency evidence useful without logging a raw room code."""
    _clear_trace_flags(monkeypatch)
    messages = []
    monkeypatch.setattr(
        websocket_routes.logger,
        "info",
        lambda template, *values: messages.append(template % values),
    )
    with TestClient(app) as client:
        room_code, _ = _join_room(client)

    assert len(messages) == 1
    message = messages[0]
    assert room_code not in message
    assert " room=" not in message
    for field in (
        "game=dice",
        "setup_ms=",
        "client_join_wait_ms=",
        "auth_ms=",
        "membership_ms=",
        "manager_join_ms=",
        "total_ms=",
    ):
        assert field in message


def test_settlement_tree_notification_and_privacy(monkeypatch):
    """Export the real settlement stages while keeping all business data private."""
    _set_trace_flags(monkeypatch)
    exporter = InMemorySpanExporter()
    assert configure_tracing(span_exporter=exporter)
    record = game_settlement_service.persist_completed_game(_settlement_event())
    assert record.settlement_status == "complete"
    assert force_flush_tracing()

    spans = exporter.get_finished_spans()
    by_name = {}
    for span in spans:
        by_name.setdefault(span.name, []).append(span)
    parent = by_name["game.settlement"][0]
    for name in (
        "game.settlement.persist",
        "game.settlement.reward",
        "game.settlement.replay",
        "game.settlement.notification",
        "game.settlement.finalize",
    ):
        assert by_name[name][0].parent.span_id == parent.context.span_id
    notification_parent = by_name["game.settlement.notification"][0]
    assert by_name["notification.persist"]
    assert all(
        span.parent.span_id == notification_parent.context.span_id
        for span in by_name["notification.persist"]
    )
    exported = _span_material(spans)
    assert all(sentinel not in exported for sentinel in SENTINELS)


def test_attribute_allow_list_rejects_secret_and_high_cardinality_values(monkeypatch):
    """Drop forbidden keys and sentinel values before they reach an exporter."""
    _set_trace_flags(monkeypatch)
    exporter = InMemorySpanExporter()
    assert configure_tracing(span_exporter=exporter)
    with trace_span(
        "game.websocket.join",
        {
            "game.type": "ROOM_CODE_SENTINEL",
            "customer.id": "CUSTOMER_TOKEN_SENTINEL",
            "result": "ADMIN_SECRET_SENTINEL",
        },
    ) as span:
        set_span_attribute(span, "database.url", "DATABASE_PASSWORD_SENTINEL")
        set_span_attribute(span, "s3.secret", "S3_SECRET_SENTINEL")
        set_span_attribute(span, "result", "success")
    exported = _span_material(exporter.get_finished_spans())
    assert all(sentinel not in exported for sentinel in SENTINELS)


def test_exporter_failure_does_not_change_notification_result(monkeypatch):
    """Rely on the SDK processor to contain an exporter outage at span end."""
    _set_trace_flags(monkeypatch)
    assert configure_tracing(span_exporter=FailingSpanExporter())
    user_code = f"gf_trace_notify_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        item = notification_service.create_notification(
            db,
            user_code,
            "TRACE_TEST",
            "测试通知",
            "业务提交不能受 exporter 影响",
            trace_persist=True,
        )
        assert item.id is not None


def test_console_mode_emits_join_and_settlement_trees_without_secrets(monkeypatch):
    """Run the explicit development console gate entirely on local test data."""
    _set_trace_flags(monkeypatch, console=True)
    output = StringIO()
    assert configure_tracing(console_output=output)
    with TestClient(app) as client:
        _join_room(client)
        game_settlement_service.persist_completed_game(_settlement_event())
    rendered = output.getvalue()
    for name in (
        "game.websocket.join",
        "game.lease.acquire",
        "game.snapshot.load",
        "game.settlement",
        "game.settlement.persist",
        "game.settlement.notification",
        "notification.persist",
        "game.settlement.finalize",
    ):
        assert f'"name": "{name}"' in rendered
    assert all(sentinel not in rendered for sentinel in SENTINELS)
