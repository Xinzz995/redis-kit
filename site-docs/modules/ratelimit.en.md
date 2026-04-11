# Rate Limiter

Distributed rate limiting based on token bucket and sliding window algorithms.

## Token Bucket

Smooths traffic with burst tolerance.

```python
from redis_kit import TokenBucketLimiter

limiter = TokenBucketLimiter(conn.sync_client, rate=10, capacity=50)
result = limiter.acquire("user:123")

if not result.allowed:
    print(f"Rate limited, retry after {result.retry_after:.1f}s")
```

## Sliding Window

Strict counting within a time window.

```python
from redis_kit import SlidingWindowLimiter

limiter = SlidingWindowLimiter(conn.sync_client, limit=100, window=60)
result = limiter.acquire("user:123")
```

## RateLimitResult

```python
result.allowed      # bool
result.limit        # Total limit
result.remaining    # Remaining quota
result.retry_after  # Seconds to wait (if rejected)
result.reset_at     # Window reset timestamp
```

Maps to HTTP response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`, `X-RateLimit-Reset`.

## @rate_limit Decorator

```python
from redis_kit import rate_limit

@rate_limit(conn.sync_client, key="api:{user_id}", limit="100/minute")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# Token bucket algorithm
@rate_limit(conn.async_client, key="api:{uid}", limit="10/second", algorithm="token_bucket")
async def get_product(uid: int) -> dict:
    return await db.query_product(uid)
```

Supported DSL formats: `"100/minute"`, `"10/second"`, `"1000/hour"`, `"10000/day"`.

Raises `RateLimitExceeded` exception when rejected, with a `.result` attribute.
