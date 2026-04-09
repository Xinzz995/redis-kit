# Observability

## MetricsCollector

```python
from redis_kit import Cache, MetricsCollector

metrics = MetricsCollector()
cache = Cache(conn.sync_client, prefix="myapp", hooks=[metrics])

# After operations...
metrics.command_count("GET")
metrics.error_count()
metrics.latency_stats()  # {"count": N, "avg": X, "min": Y, "max": Z}
```

## OpenTelemetry

Requires `pip install redis-py-kit[otel]`.

```python
from redis_kit.observability import OpenTelemetryHook

hook = OpenTelemetryHook(service_name="myapp")
cache = Cache(conn.sync_client, hooks=[hook])
# Every Redis operation creates an OTel span
```

## CommandHook Protocol

Create custom hooks:

```python
class MyHook:
    def before(self, command: str, key: str, args: tuple) -> None: ...
    def after(self, command: str, key: str, result, duration_ms: float) -> None: ...
    def on_error(self, command: str, key: str, error: Exception) -> None: ...
```

## CompositeHook

Chain multiple hooks:

```python
from redis_kit import CompositeHook

hook = CompositeHook(metrics, otel_hook, my_hook)
cache = Cache(conn.sync_client, hooks=[hook])
```
