from redis_kit.observability.metrics import MetricsCollector

__all__ = ["MetricsCollector"]

try:
    from redis_kit.observability.otel import OpenTelemetryHook

    __all__ += ["OpenTelemetryHook"]
except ImportError:
    pass
