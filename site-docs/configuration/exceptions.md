# 异常处理

## 异常层次结构

```
RedisKitError
├── RedisConnectionError
│   └── ConnectionPoolExhaustedError
├── SerializationError
├── TopologyConstraintError
├── LockError
│   ├── LockAcquireError
│   └── LockReleaseError
├── CacheError
├── QueueError
│   └── QueueEmptyError
├── BloomFilterError
├── SessionError
│   └── SessionNotFoundError
├── RateLimitExceeded
├── StreamError
└── RepositoryError
    ├── EntityNotFoundError
    └── OptimisticLockError
```

## 降级策略（FallbackPolicy）

可配置的 Redis 故障降级策略。

```python
from redis_kit import FallbackPolicy, Cache

policy = FallbackPolicy(
    on_connection_error="return_none",  # "raise" | "return_none" | "callback"
    log_on_fallback=True,
)
cache = Cache(conn.sync_client, fallback_policy=policy)
```

### 模式

| 模式 | 行为 |
|------|------|
| `"raise"`（默认） | 重新抛出异常 |
| `"return_none"` | 记录警告日志，返回 None |
| `"callback"` | 调用 `fallback` 回调函数并返回其结果 |

### Callback 示例

```python
from redis_kit import Cache, FallbackPolicy

def local_fallback(command: str, key: str, error: Exception):
    """Redis 不可用时从本地缓存降级"""
    if command == "GET":
        return local_cache.get(key)
    return None

policy = FallbackPolicy(
    on_connection_error="callback",
    fallback=local_fallback,
)
cache = Cache(conn.sync_client, prefix="myapp", fallback_policy=policy)
```

!!! note "仅对连接类异常生效"
    FallbackPolicy 仅在 `RedisConnectionError` 和 `RedisTimeoutError` 时触发。其他异常（如序列化错误）始终直接抛出。

!!! warning "callback 模式必须提供 fallback"
    使用 `on_connection_error="callback"` 时，必须同时提供 `fallback` 回调函数，否则构造时会抛出 `ValueError`。
