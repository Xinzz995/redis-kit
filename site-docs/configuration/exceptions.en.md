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
| `"return_none"` | Swallows the error, returns None |
| `"callback"` | Calls the `fallback` function and returns its result |
