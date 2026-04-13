# 可观测性

## MetricsCollector

```python
from redis_kit import Cache, MetricsCollector

metrics = MetricsCollector()
cache = Cache(conn.sync_client, prefix="myapp", hooks=[metrics])

# After operations...
metrics.command_count("GET")
metrics.error_count()              # 总错误数
metrics.error_count(command="GET") # 按命令过滤的错误数
metrics.latency_stats()  # {"count": N, "avg": X, "min": Y, "max": Z}
```

## OpenTelemetry

需要安装 `pip install redis-py-kit[otel]`。

```python
from redis_kit.observability import OpenTelemetryHook

hook = OpenTelemetryHook(service_name="myapp")
cache = Cache(conn.sync_client, hooks=[hook])
# Every Redis operation creates an OTel span
```

## CommandHook 协议

创建自定义 Hook：

```python
class MyHook:
    def before(self, command: str, key: str, args: tuple) -> None: ...
    def after(self, command: str, key: str, result, duration_ms: float) -> None: ...
    def on_error(self, command: str, key: str, error: Exception) -> None: ...
```

## CompositeHook

链式组合多个 Hook：

```python
from redis_kit import CompositeHook

hook = CompositeHook(metrics, otel_hook, my_hook)
cache = Cache(conn.sync_client, hooks=[hook])
```
