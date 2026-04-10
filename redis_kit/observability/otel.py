from __future__ import annotations

import contextvars
from typing import Any

try:
    from opentelemetry import trace

    _current_span_var: contextvars.ContextVar[trace.Span | None] = contextvars.ContextVar("_otel_span", default=None)

    class OpenTelemetryHook:
        """Creates OpenTelemetry spans for Redis operations."""

        def __init__(self, service_name: str = "redis-kit") -> None:
            self._tracer = trace.get_tracer(service_name)

        def before(self, command: str, key: str, args: tuple) -> None:
            span = self._tracer.start_span(f"redis.{command.lower()}")
            span.set_attribute("db.system", "redis")
            span.set_attribute("db.operation", command)
            span.set_attribute("db.redis.key", key)
            _current_span_var.set(span)

        def after(self, command: str, key: str, result: Any, duration_ms: float) -> None:
            span = _current_span_var.get()
            if span is not None:
                span.set_attribute("db.redis.duration_ms", duration_ms)
                span.end()
                _current_span_var.set(None)

        def on_error(self, command: str, key: str, error: Exception) -> None:
            span = _current_span_var.get()
            if span is not None:
                span.record_exception(error)
                span.set_status(trace.StatusCode.ERROR, str(error))
                span.end()
                _current_span_var.set(None)

except ImportError:
    pass
