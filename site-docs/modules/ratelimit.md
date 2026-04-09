# 限流器

基于令牌桶和滑动窗口算法的分布式限流。

## 令牌桶（Token Bucket）

平滑流量，支持突发容忍。

```python
from redis_kit import TokenBucketLimiter

limiter = TokenBucketLimiter(conn.sync_client, rate=10, capacity=50)
result = limiter.acquire("user:123")

if not result.allowed:
    print(f"Rate limited, retry after {result.retry_after:.1f}s")
```

## 滑动窗口（Sliding Window）

在时间窗口内进行严格计数。

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

映射到 HTTP 响应头：`X-RateLimit-Limit`、`X-RateLimit-Remaining`、`Retry-After`、`X-RateLimit-Reset`。

## @rate_limit 装饰器

```python
from redis_kit import rate_limit

@rate_limit(conn.sync_client, key="api:{user_id}", limit="100/minute")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# Token bucket algorithm
@rate_limit(conn.sync_client, key="api:{uid}", limit="10/second", algorithm="token_bucket")
async def get_product(uid: int) -> dict:
    return await db.query_product(uid)
```

支持的 DSL 格式：`"100/minute"`、`"10/second"`、`"1000/hour"`、`"10000/day"`。

被拒绝时抛出 `RateLimitExceeded` 异常，包含 `.result` 属性。
