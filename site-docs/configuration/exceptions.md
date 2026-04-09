# Exception Handling

## Hierarchy

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

## FallbackPolicy

Configurable degradation for Redis failures.

```python
from redis_kit import FallbackPolicy, Cache

policy = FallbackPolicy(
    on_connection_error="return_none",  # "raise" | "return_none" | "callback"
    log_on_fallback=True,
)
cache = Cache(conn.sync_client, fallback_policy=policy)
```

### Modes

| Mode | Behavior |
|------|----------|
| `"raise"` (default) | Re-raise the exception |
| `"return_none"` | Swallow error, return None |
| `"callback"` | Call `fallback` function and return its result |
