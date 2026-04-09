from __future__ import annotations

from typing import Any

try:
    from opentelemetry import trace

    class OpenTelemetryHook:
        """Creates OpenTelemetry spans for Redis operations."""

        def __init__(self, service_name: str = "redis-kit") -> None:
            self._tracer = trace.get_tracer(service_name)

        def before(self, command: str, key: str, args: tuple) -> None:
            pass

        def after(self, command: str, key: str, result: Any, duration_ms: float) -> None:
            with self._tracer.start_as_current_span(f"redis.{command.lower()}") as span:
                span.set_attribute("db.system", "redis")
                span.set_attribute("db.operation", command)
                span.set_attribute("db.redis.key", key)
                span.set_attribute("db.redis.duration_ms", duration_ms)

        def on_error(self, command: str, key: str, error: Exception) -> None:
            with self._tracer.start_as_current_span(f"redis.{command.lower()}") as span:
                span.set_attribute("db.system", "redis")
                span.set_attribute("db.operation", command)
                span.set_attribute("db.redis.key", key)
                span.record_exception(error)
                span.set_status(trace.StatusCode.ERROR, str(error))

except ImportError:
    pass
