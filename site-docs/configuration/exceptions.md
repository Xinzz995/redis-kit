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
| `"return_none"` | 吞掉错误，返回 None |
| `"callback"` | 调用 `fallback` 函数并返回其结果 |
