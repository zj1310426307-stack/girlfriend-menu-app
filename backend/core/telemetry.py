"""Optional, privacy-safe OpenTelemetry trace boundary for LoveOS.

The API remains no-op until application startup explicitly enables the SDK.
Business modules create only allow-listed spans and attributes through this
module; exporter construction and provider ownership stay centralized here.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import logging
import sys
from threading import Lock
from typing import IO

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)

from core.settings import get_settings


logger = logging.getLogger(__name__)
INSTRUMENTATION_NAME = "loveos.backend"
INSTRUMENTATION_VERSION = "3.0"

ALLOWED_SPAN_NAMES = frozenset(
    {
        "telemetry.test",
        "game.websocket.join",
        "game.snapshot.load",
        "game.lease.acquire",
        "game.settlement",
        "game.settlement.persist",
        "game.settlement.reward",
        "game.settlement.replay",
        "game.settlement.notification",
        "game.settlement.finalize",
        "notification.persist",
    }
)
ALLOWED_SPAN_ATTRIBUTES = frozenset(
    {
        "game.type",
        "state.source",
        "result",
        "retry.count",
        "reconnect",
        "settlement.stage",
    }
)
ALLOWED_GAME_TYPES = frozenset(
    {"animal", "chess", "dice", "flight", "gomoku", "landlord", "unknown"}
)
ALLOWED_STATE_SOURCES = frozenset({"postgresql", "redis", "memory", "none"})
ALLOWED_RESULTS = frozenset(
    {
        "acquired",
        "busy",
        "created",
        "error",
        "existing",
        "hit",
        "miss",
        "rejected",
        "success",
        "unauthorized",
    }
)
ALLOWED_SETTLEMENT_STAGES = frozenset(
    {"persist", "reward", "replay", "notification", "finalize"}
)

_provider: TracerProvider | None = None
_provider_lock = Lock()
_noop_tracer = trace.NoOpTracerProvider().get_tracer(
    INSTRUMENTATION_NAME,
    INSTRUMENTATION_VERSION,
)


def _safe_attribute(key: str, value: object) -> tuple[str, object] | None:
    """Validate one low-cardinality attribute without stringifying user data."""
    if key not in ALLOWED_SPAN_ATTRIBUTES:
        return None
    if key == "game.type":
        normalized = value.lower() if isinstance(value, str) else ""
        return (key, normalized) if normalized in ALLOWED_GAME_TYPES else None
    if key == "state.source":
        return (key, value) if value in ALLOWED_STATE_SOURCES else None
    if key == "result":
        return (key, value) if value in ALLOWED_RESULTS else None
    if key == "settlement.stage":
        return (key, value) if value in ALLOWED_SETTLEMENT_STAGES else None
    if key == "reconnect":
        return (key, value) if isinstance(value, bool) else None
    if key == "retry.count" and isinstance(value, int) and not isinstance(value, bool):
        return key, min(max(value, 0), 10)
    return None


def _safe_attributes(attributes: Mapping[str, object] | None) -> dict[str, object]:
    """Drop every attribute outside the explicit privacy and cardinality allow-list."""
    safe: dict[str, object] = {}
    for key, value in (attributes or {}).items():
        item = _safe_attribute(key, value)
        if item is not None:
            safe[item[0]] = item[1]
    return safe


def configure_tracing(
    *,
    span_exporter: SpanExporter | None = None,
    console_output: IO[str] | None = None,
) -> bool:
    """Initialize the one trace provider only after explicit startup opt-in.

    ``span_exporter`` is an injection point for tests and a future reviewed
    deployment exporter. R2B1 creates only the SDK's console exporter, and only
    when a second explicit flag is enabled outside production.
    """
    global _provider

    with _provider_lock:
        if _provider is not None:
            return True
        try:
            settings = get_settings()
            if not settings.tracing_enabled:
                return False
            exporter = span_exporter
            if (
                exporter is None
                and settings.tracing_console_enabled
                and not settings.is_production
            ):
                exporter = ConsoleSpanExporter(out=console_output or sys.stdout)
            provider = TracerProvider(
                resource=Resource.create(
                    {"service.name": settings.tracing_service_name}
                ),
                shutdown_on_exit=False,
            )
            if exporter is not None:
                # The SDK processor isolates exporter exceptions from span end.
                provider.add_span_processor(SimpleSpanProcessor(exporter))
            _provider = provider
            return True
        except Exception:
            # Telemetry setup must never become an application startup dependency.
            logger.warning("telemetry initialization failed; tracing remains disabled")
            _provider = None
            return False


def tracing_enabled() -> bool:
    """Report whether the local optional SDK provider is currently active."""
    return _provider is not None


def shutdown_tracing() -> None:
    """Flush and release the optional provider without affecting app shutdown."""
    global _provider

    with _provider_lock:
        provider = _provider
        _provider = None
    if provider is None:
        return
    try:
        provider.shutdown()
    except Exception:
        logger.warning("telemetry shutdown failed")


def force_flush_tracing(timeout_millis: int = 30000) -> bool:
    """Flush test/development spans while treating exporter failure as non-fatal."""
    provider = _provider
    if provider is None:
        return True
    try:
        return provider.force_flush(timeout_millis=timeout_millis)
    except Exception:
        logger.warning("telemetry flush failed")
        return False


def set_span_attribute(span: trace.Span, key: str, value: object) -> None:
    """Set one attribute only when its key and value pass the central allow-list."""
    item = _safe_attribute(key, value)
    if item is None:
        return
    try:
        span.set_attribute(item[0], item[1])
    except Exception:
        logger.warning("telemetry attribute update failed")


@contextmanager
def trace_span(
    name: str,
    attributes: Mapping[str, object] | None = None,
) -> Iterator[trace.Span]:
    """Create one safe current span while preserving every business exception."""
    safe_name = name if name in ALLOWED_SPAN_NAMES else "telemetry.test"
    provider = _provider
    tracer = (
        provider.get_tracer(INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION)
        if provider is not None
        else _noop_tracer
    )
    try:
        scope = tracer.start_as_current_span(
            safe_name,
            attributes=_safe_attributes(attributes),
            record_exception=False,
            set_status_on_exception=False,
        )
        span = scope.__enter__()
    except Exception:
        logger.warning("telemetry span start failed name=%s", safe_name)
        yield _noop_tracer.start_span(safe_name)
        return

    try:
        yield span
    except BaseException:
        set_span_attribute(span, "result", "error")
        try:
            scope.__exit__(*sys.exc_info())
        except Exception:
            logger.warning("telemetry span end failed name=%s", safe_name)
        raise
    else:
        try:
            scope.__exit__(None, None, None)
        except Exception:
            logger.warning("telemetry span end failed name=%s", safe_name)
