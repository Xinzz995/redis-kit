# Exception Handling

## Exception Hierarchy

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

## Fallback Policy

Configurable degradation strategy for Redis failures.

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
| `"raise"` (default) | Re-raises the exception |
| `"return_none"` | Logs a warning, returns None |
| `"callback"` | Calls the `fallback` function and returns its result |

### Callback Example

```python
from redis_kit import Cache, FallbackPolicy

def local_fallback(command: str, key: str, error: Exception):
    """Fall back to local cache when Redis is unavailable"""
    if command == "GET":
        return local_cache.get(key)
    return None

policy = FallbackPolicy(
    on_connection_error="callback",
    fallback=local_fallback,
)
cache = Cache(conn.sync_client, prefix="myapp", fallback_policy=policy)
```

!!! note "Only triggers for connection errors"
    FallbackPolicy only activates for `RedisConnectionError` and `RedisTimeoutError`. Other exceptions (e.g., serialization errors) are always re-raised.

!!! warning "callback mode requires a fallback"
    When using `on_connection_error="callback"`, you must provide a `fallback` callable. Omitting it raises `ValueError` at construction time.
