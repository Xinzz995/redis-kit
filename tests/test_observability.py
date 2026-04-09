from redis_kit.hooks import CommandHook
from redis_kit.observability.metrics import MetricsCollector


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
