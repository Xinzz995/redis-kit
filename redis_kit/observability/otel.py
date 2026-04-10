from __future__ import annotations

import contextvars
from typing import Any

try:
    from opentelemetry import trace

    _span_stack_var: contextvars.ContextVar[list[trace.Span]] = contextvars.ContextVar("_otel_span_stack")

    class OpenTelemetryHook:
        """Creates OpenTelemetry spans for Redis operations."""

        def __init__(self, service_name: str = "redis-kit") -> None:
            self._tracer = trace.get_tracer(service_name)

        def before(self, command: str, key: str, args: tuple) -> None:
            span = self._tracer.start_span(f"redis.{command.lower()}")
            span.set_attribute("db.system", "redis")
            span.set_attribute("db.operation", command)
            span.set_attribute("db.redis.key", key)
            try:
                stack = _span_stack_var.get()
            except LookupError:
                stack = []
                _span_stack_var.set(stack)
            stack.append(span)

        def after(self, command: str, key: str, result: Any, duration_ms: float) -> None:
            try:
                stack = _span_stack_var.get()
            except LookupError:
                return
            if not stack:
                return
            span = stack.pop()
            span.set_attribute("db.redis.duration_ms", duration_ms)
            span.end()

        def on_error(self, command: str, key: str, error: Exception) -> None:
            try:
                stack = _span_stack_var.get()
            except LookupError:
                return
            if not stack:
                return
            span = stack.pop()
            span.record_exception(error)
            span.set_status(trace.StatusCode.ERROR, str(error))
            span.end()

except ImportError:
    pass
