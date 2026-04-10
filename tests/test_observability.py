import pytest

from redis_kit.hooks import CommandHook
from redis_kit.observability.metrics import MetricsCollector

try:
    from unittest.mock import MagicMock, patch

    from opentelemetry import trace  # noqa: F401

    _otel_available = True
except ImportError:
    _otel_available = False

pytestmark_otel = pytest.mark.skipif(not _otel_available, reason="opentelemetry not installed")


@pytestmark_otel
class TestOpenTelemetryHook:
    def _make_hook(self):
        from redis_kit.observability.otel import OpenTelemetryHook

        return OpenTelemetryHook()

    def _make_mock_span(self):
        span = MagicMock()
        span.set_attribute = MagicMock()
        span.end = MagicMock()
        span.record_exception = MagicMock()
        span.set_status = MagicMock()
        return span

    def test_before_pushes_span_onto_stack(self):
        """before() should push a new span onto the stack."""
        from redis_kit.observability import otel as otel_module

        hook = self._make_hook()
        span1 = self._make_mock_span()

        with patch.object(hook._tracer, "start_span", return_value=span1):
            hook.before("GET", "key:1", ())

        try:
            stack = otel_module._span_stack_var.get()
        except LookupError:
            stack = []
        assert span1 in stack

    def test_after_pops_span_and_ends_it(self):
        """after() should pop the most recent span and call end()."""
        hook = self._make_hook()
        span1 = self._make_mock_span()

        with patch.object(hook._tracer, "start_span", return_value=span1):
            hook.before("GET", "key:1", ())

        hook.after("GET", "key:1", "value", 5.0)
        span1.end.assert_called_once()
        span1.set_attribute.assert_any_call("db.redis.duration_ms", 5.0)

    def test_on_error_pops_span_records_exception_and_ends_it(self):
        """on_error() should pop the span, record exception, set error status, and end it."""
        hook = self._make_hook()
        span1 = self._make_mock_span()
        err = RuntimeError("connection failed")

        with patch.object(hook._tracer, "start_span", return_value=span1):
            hook.before("GET", "key:1", ())

        hook.on_error("GET", "key:1", err)
        span1.record_exception.assert_called_once_with(err)
        span1.end.assert_called_once()

    def test_concurrent_spans_both_ended(self):
        """Two before() calls followed by two after() calls must both end their spans.

        This is the regression test for the span-leak bug where the old single-span
        ContextVar caused the first span to be overwritten before it could be ended.
        """
        hook = self._make_hook()
        span1 = self._make_mock_span()
        span2 = self._make_mock_span()

        spans = [span1, span2]
        call_count = 0

        def fake_start_span(name, **kwargs):
            nonlocal call_count
            s = spans[call_count]
            call_count += 1
            return s

        with patch.object(hook._tracer, "start_span", side_effect=fake_start_span):
            # Simulate two concurrent operations both calling before() before either calls after()
            hook.before("GET", "key:1", ())
            hook.before("SET", "key:2", ())

        # Both operations complete — LIFO order (stack)
        hook.after("SET", "key:2", "ok", 3.0)
        hook.after("GET", "key:1", "val", 7.0)

        span1.end.assert_called_once()
        span2.end.assert_called_once()

    def test_after_without_before_is_safe(self):
        """after() with an empty stack should not raise."""
        hook = self._make_hook()
        hook.after("GET", "key:missing", None, 1.0)  # Should not raise

    def test_on_error_without_before_is_safe(self):
        """on_error() with an empty stack should not raise."""
        hook = self._make_hook()
        hook.on_error("GET", "key:missing", RuntimeError("boom"))  # Should not raise


class TestMetricsCollector:
    def test_conforms_to_hook_protocol(self):
        assert isinstance(MetricsCollector(), CommandHook)

    def test_records_commands(self):
        m = MetricsCollector()
        m.after("GET", "user:1", "value", 1.5)
        m.after("GET", "user:2", "value", 2.0)
        m.after("SET", "user:3", None, 0.5)
        assert m.command_count("GET") == 2
        assert m.command_count("SET") == 1

    def test_records_errors(self):
        m = MetricsCollector()
        m.on_error("GET", "user:1", RuntimeError("fail"))
        assert m.error_count() == 1

    def test_latency_stats(self):
        m = MetricsCollector()
        m.after("GET", "k", "v", 1.0)
        m.after("GET", "k", "v", 3.0)
        m.after("GET", "k", "v", 2.0)
        stats = m.latency_stats()
        assert stats["count"] == 3
        assert stats["avg"] == 2.0
        assert stats["min"] == 1.0
        assert stats["max"] == 3.0

    def test_before_is_noop(self):
        m = MetricsCollector()
        m.before("GET", "k", ())  # Should not raise
