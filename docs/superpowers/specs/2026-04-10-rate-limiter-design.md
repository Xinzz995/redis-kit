# redis-py-kit 限流器模块设计

## 1. 概述

为 redis-py-kit 添加分布式限流器模块，支持令牌桶和滑动窗口两种算法，提供编程式 API 和 `@rate_limit` 装饰器。所有 Redis 操作通过 Lua 脚本保证原子性。

### 使用场景

- API 网关限流：按 IP / 用户 / API key 限制请求频率
- 业务级限流：短信发送频率、下单频率、登录尝试次数

### 设计参考

| 来源 | 借鉴内容 |
|------|---------|
| limits (Python) | Lua 脚本原子操作；Sorted Set 滑动窗口；hash tag 保证 Cluster 安全 |
| redis-cell | 5 字段返回值（allowed, limit, remaining, retry_after, reset）→ HTTP 限流头 |
| Spring Cloud Gateway | 令牌桶 Lua 脚本：tokens + timestamp 双 key，TTL 自清理 |
| slowapi | `"100/minute"` DSL 字符串格式 |

## 2. 文件结构

```
redis_kit/ratelimit/
├── __init__.py                  # 导出所有公共类
├── _lua.py                      # Lua 脚本常量
├── _result.py                   # RateLimitResult 数据类
├── token_bucket.py              # TokenBucketLimiter (sync)
├── async_token_bucket.py        # AsyncTokenBucketLimiter
├── sliding_window.py            # SlidingWindowLimiter (sync)
├── async_sliding_window.py      # AsyncSlidingWindowLimiter
└── decorator.py                 # @rate_limit 装饰器
```

## 3. 核心数据类

### RateLimitResult

```python
@dataclass(frozen=True)
class RateLimitResult:
    """Rate limit check result, maps to standard HTTP rate limit headers."""

    allowed: bool           # 是否放行
    limit: int              # 窗口/桶容量上限
    remaining: int          # 剩余配额
    retry_after: float      # 被拒时需等待秒数，0.0 表示不需要等待
    reset_at: float         # 窗口/桶重置的 Unix 时间戳
```

字段直接对应 HTTP 限流响应头：

| 字段 | HTTP Header |
|------|------------|
| `limit` | `X-RateLimit-Limit` |
| `remaining` | `X-RateLimit-Remaining` |
| `retry_after` | `Retry-After` |
| `reset_at` | `X-RateLimit-Reset` |

## 4. 异常

```python
class RateLimitExceeded(RedisKitError):
    """Rate limit exceeded."""

    def __init__(self, result: RateLimitResult) -> None:
        self.result = result
        super().__init__(
            f"Rate limit exceeded: {result.remaining}/{result.limit}, "
            f"retry after {result.retry_after:.1f}s"
        )
```

## 5. 令牌桶算法 — TokenBucketLimiter

### 原理

- 桶以固定速率 `rate`（每秒）补充令牌，最多持有 `capacity` 个
- 每次请求消耗 1 个令牌（可配置 cost）
- 令牌不足时拒绝
- 适合平滑流量并允许突发

### Redis 实现

两个 key（借鉴 Spring Cloud Gateway）：

- `{prefix}:{key}:tokens` — 当前令牌数（String）
- `{prefix}:{key}:ts` — 上次补充时间戳（String）

使用 `{hash_tag}` 前缀保证 Cluster 下两个 key 在同一 slot。

TTL = `ceil(capacity / rate) * 2` — 令牌桶填满所需时间的 2 倍，自动清理不活跃的 key。

### Lua 脚本

```lua
local tokens_key = KEYS[1]
local ts_key = KEYS[2]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local last_tokens = tonumber(redis.call("get", tokens_key))
if last_tokens == nil then
    last_tokens = capacity
end

local last_ts = tonumber(redis.call("get", ts_key))
if last_ts == nil then
    last_ts = now
end

local delta = math.max(0, now - last_ts)
local filled = math.min(capacity, last_tokens + delta * rate)
local allowed = filled >= cost
local new_tokens = filled
local retry_after = 0
local reset_at = now + (capacity - filled) / rate

if allowed then
    new_tokens = filled - cost
else
    retry_after = (cost - filled) / rate
end

redis.call("setex", tokens_key, ttl, new_tokens)
redis.call("setex", ts_key, ttl, now)

return {allowed and 1 or 0, capacity, math.floor(new_tokens), math.floor(retry_after * 1000), math.floor(reset_at * 1000)}
```

返回值：`[allowed(0/1), limit, remaining, retry_after_ms, reset_at_ms]`

### API

```python
class TokenBucketLimiter:
    def __init__(
        self,
        client: redis.Redis,
        prefix: str = "redis_kit:rl:tb",
        rate: float = 10.0,       # 每秒补充令牌数
        capacity: int = 50,        # 桶容量
    ) -> None: ...

    def acquire(self, key: str, cost: int = 1) -> RateLimitResult: ...

    def reset(self, key: str) -> None: ...
```

## 6. 滑动窗口算法 — SlidingWindowLimiter

### 原理

- 在 `window` 秒的滑动时间窗口内，最多允许 `limit` 次请求
- 精确计数，无近似
- 适合严格的频率限制

### Redis 实现

一个 Sorted Set（借鉴 limits）：

- key: `{prefix}:{key}`
- member: 唯一 ID（`{timestamp}:{random}`）
- score: 请求时间戳

### Lua 脚本

```lua
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

-- 移除窗口外的记录
redis.call("zremrangebyscore", key, "-inf", now - window * 1000)

-- 当前窗口内的请求数
local count = redis.call("zcard", key)

local allowed = count < limit
local remaining = math.max(0, limit - count - 1)
local retry_after = 0
local reset_at = now + window * 1000

if allowed then
    redis.call("zadd", key, now, member)
    redis.call("pexpire", key, ttl)
else
    remaining = 0
    -- 计算最早记录过期的时间
    local oldest = redis.call("zrange", key, 0, 0, "WITHSCORES")
    if #oldest > 0 then
        retry_after = oldest[2] + window * 1000 - now
        reset_at = oldest[2] + window * 1000
    end
end

return {allowed and 1 or 0, limit, remaining, math.floor(retry_after), math.floor(reset_at)}
```

注意：Lua 内部使用毫秒精度避免浮点数问题。

### API

```python
class SlidingWindowLimiter:
    def __init__(
        self,
        client: redis.Redis,
        prefix: str = "redis_kit:rl:sw",
        limit: int = 100,         # 窗口内最大请求数
        window: int = 60,          # 窗口大小（秒）
    ) -> None: ...

    def acquire(self, key: str) -> RateLimitResult: ...

    def reset(self, key: str) -> None: ...
```

## 7. @rate_limit 装饰器

```python
@rate_limit(
    client,
    key="api:{user_id}",              # 字符串模板或 callable
    limit="100/minute",                # DSL 字符串
    algorithm="sliding_window",        # "token_bucket" | "sliding_window"
)
def get_user(user_id: int) -> dict:
    return db.query(user_id)

# 异步函数自动检测
@rate_limit(client, key="api:{uid}", limit="10/second", algorithm="token_bucket")
async def get_product(uid: int) -> dict:
    return await db.query(uid)
```

### DSL 格式解析

`"100/minute"` → limit=100, window=60

支持的时间单位：`second(s)`, `minute(s)`, `hour(s)`, `day(s)`

### 被拒行为

装饰器在限流被拒时抛出 `RateLimitExceeded` 异常，包含 `result` 属性。调用方可以 catch 并转换为 HTTP 429 响应。

## 8. 异步变体

`AsyncTokenBucketLimiter` 和 `AsyncSlidingWindowLimiter` 提供完全对称的异步 API：

```python
result = await async_limiter.acquire("user:123")
```

## 9. Cluster 兼容

- 令牌桶：两个 key 使用 `{hash_tag}` 前缀保证同 slot
- 滑动窗口：单 key 操作，天然兼容

## 10. 公共 API 导出

```python
from redis_kit import (
    TokenBucketLimiter, AsyncTokenBucketLimiter,
    SlidingWindowLimiter, AsyncSlidingWindowLimiter,
    RateLimitResult, RateLimitExceeded,
    rate_limit,
)
```

## 11. 用户使用示例

```python
from redis_kit import ConnectionManager, TokenBucketLimiter, SlidingWindowLimiter

conn = ConnectionManager(url="redis://localhost:6379/0")

# 令牌桶 — API 网关，允许突发
api_limiter = TokenBucketLimiter(
    conn.sync_client,
    prefix="gateway:rl",
    rate=10,           # 每秒 10 个令牌
    capacity=50,       # 最多突发 50 个
)

result = api_limiter.acquire("ip:192.168.1.1")
if not result.allowed:
    print(f"Too many requests, retry after {result.retry_after:.1f}s")

# 滑动窗口 — 业务限流，严格计数
sms_limiter = SlidingWindowLimiter(
    conn.sync_client,
    prefix="sms:rl",
    limit=5,           # 每分钟最多 5 条
    window=60,
)

result = sms_limiter.acquire("phone:13800138000")
```
