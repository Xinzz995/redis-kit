# redis-kit Design Spec

## 1. Overview

redis-kit is a comprehensive, enterprise-grade Python Redis toolkit library. It provides caching, distributed locks, message queues, bloom filters, counters/ID generators, and session management with both sync and async APIs.

- **Target**: Internal use + open-source PyPI package
- **Python**: >= 3.11
- **Redis driver**: redis-py >= 7.4.0
- **v1 scope**: Standalone mode only (Sentinel/Cluster deferred to v2)

## 2. Architecture

Independent modules + shared connection via dependency injection (方案 B).

```
redis_kit/
├── __init__.py                # Public API exports
├── connection.py              # ConnectionManager (sync/async views)
├── config.py                  # Frozen dataclass configs
├── serializers/
│   ├── __init__.py
│   ├── base.py                # Serializer protocol
│   ├── json.py                # JsonSerializer
│   ├── msgpack.py             # MsgpackSerializer
│   └── pickle.py              # PickleSerializer
├── compressors/
│   ├── __init__.py
│   ├── base.py                # Compressor protocol
│   ├── zstd.py                # ZstdCompressor
│   ├── lz4.py                 # Lz4Compressor
│   └── zlib.py                # ZlibCompressor
├── cache/
│   ├── __init__.py
│   ├── _logic.py              # Shared non-IO logic (key building, validation)
│   ├── cache.py               # Cache (sync)
│   ├── async_cache.py         # AsyncCache
│   └── decorator.py           # @cached decorator (sync + async)
├── lock/
│   ├── __init__.py
│   ├── lock.py                # Lock (sync)
│   └── async_lock.py          # AsyncLock
├── queue/
│   ├── __init__.py
│   ├── queue.py               # Queue / DelayQueue / ReliableQueue (sync)
│   └── async_queue.py         # Async variants
├── bloom/
│   ├── __init__.py
│   ├── bloom.py               # BloomFilter (sync)
│   └── async_bloom.py         # AsyncBloomFilter
├── counter/
│   ├── __init__.py
│   ├── counter.py             # Counter + IDGenerator (sync)
│   └── async_counter.py       # Async variants
├── session/
│   ├── __init__.py
│   ├── session.py             # SessionManager (sync)
│   └── async_session.py       # AsyncSessionManager
├── hooks.py                   # CommandHook protocol + CompositeHook
├── observability/
│   ├── __init__.py
│   ├── otel.py                # OpenTelemetry integration
│   └── metrics.py             # Metrics collection
└── exceptions.py              # Exception hierarchy + FallbackPolicy
```

### Design principles

- Each module has a single responsibility and communicates through the ConnectionManager interface
- Modules are imported independently: `from redis_kit.cache import Cache`
- No global state, no singletons — all state flows through constructor injection
- Non-IO logic (key building, serialization, validation) is shared via `_logic.py` to reduce sync/async duplication
- IO logic is written separately for sync and async, keeping each class small (< 150 lines target)

## 3. Connection Management

### ConnectionManager

Central connection lifecycle manager. Provides sync/async views inspired by Lettuce.

```python
from redis_kit import ConnectionManager

# Create
conn = ConnectionManager(url="redis://localhost:6379/0")

# Or with config object
conn = ConnectionManager(config=ConnectionConfig(
    host="localhost",
    port=6379,
    db=0,
    max_connections=20,
    socket_timeout=5.0,
    decode_responses=False,
))

# Sync/async views (API sugar, underlying pools are separate)
conn.sync_client    # -> redis.Redis
conn.async_client   # -> redis.asyncio.Redis

# Lifecycle
conn.close()         # Close sync resources
await conn.aclose()  # Close async resources
```

### Key design decisions

- **Event Loop isolation**: Async clients are cached per event loop (WeakKeyDictionary), preventing cross-loop reuse. Borrowed from old codebase — this is correctness, not optional.
- **Lazy initialization**: Connection pools are created on first access, not at construction time.
- **Thread safety**: sync_client is thread-safe via connection pool. Documented explicitly.
- **v2 extension point**: Constructor will accept a `topology` parameter (standalone/sentinel/cluster) without changing the interface.

### Config

Frozen dataclasses, split by concern:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ConnectionConfig:
    url: str | None = None
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False

@dataclass(frozen=True)
class NamespaceConfig:
    prefix: str = ""
    separator: str = ":"
```

## 4. Serialization

### Serializer protocol

```python
from typing import Protocol, Any

class Serializer(Protocol):
    def dumps(self, value: Any) -> bytes: ...
    def loads(self, data: bytes) -> Any: ...
```

Unified bytes I/O. The ConnectionManager layer handles encode/decode.

### Built-in serializers

| Serializer | Format | Use case |
|-----------|--------|----------|
| JsonSerializer | JSON | Default, human-readable, interoperable |
| MsgpackSerializer | MessagePack | Compact binary, fast |
| PickleSerializer | Pickle | Python-native objects, trusted environments only |

### Compressor protocol (independent layer)

Inspired by django-redis: serializer and compressor are separate, freely combinable.

```python
class Compressor(Protocol):
    def compress(self, data: bytes) -> bytes: ...
    def decompress(self, data: bytes) -> bytes: ...
```

Built-in: ZstdCompressor, Lz4Compressor, ZlibCompressor. All optional.

Data pipeline: `value -> serializer.dumps() -> compressor.compress() -> Redis`

```python
cache = Cache(
    conn,
    serializer=JsonSerializer(),
    compressor=ZstdCompressor(),  # Optional, None = no compression
)
```

## 5. Cache Module

### Core API

```python
from redis_kit.cache import Cache, AsyncCache

cache = Cache(conn, prefix="myapp:cache", serializer=JsonSerializer())

# Basic operations
cache.set("user:1", {"name": "Alice"}, ttl=3600)
value = cache.get("user:1")
cache.delete("user:1")

# TTL management (inspired by django-redis)
cache.ttl("user:1")                    # Remaining seconds
cache.pttl("user:1")                   # Remaining milliseconds
cache.persist("user:1")                # Remove expiration
cache.expire("user:1", 600)            # Reset TTL
cache.expire_at("user:1", datetime)    # Expire at specific time

# Cache-aside pattern
value = cache.remember("user:1", factory=load_user, ttl=3600)

# Batch operations
values = cache.get_many(["user:1", "user:2", "user:3"])
cache.set_many({"user:1": data1, "user:2": data2}, ttl=3600)

# Pattern operations (SCAN-based, never KEYS)
cache.delete_pattern("user:*")
for key in cache.iter_keys("user:*"):
    ...

# Null value caching (anti-penetration)
cache.set("user:999", None, ttl=60)  # Cache null to prevent penetration
```

### Bound operations (inspired by Spring Data)

```python
user_cache = cache.bind("user:1")
user_cache.set({"name": "Alice"}, ttl=3600)
user_cache.get()
user_cache.ttl()
user_cache.expire(600)
```

### @cached decorator

```python
from redis_kit.cache import cached

@cached(
    conn,
    key="user:{user_id}",                              # String template
    # key=lambda user_id: f"user:{user_id}",           # Or callable
    ttl="2h30m",                                        # String / int / callable
    # ttl=lambda user_id: 3600 if user_id < 100 else 300,
    lock=True,                                          # Anti-breakdown: distributed lock on miss
    bypass=lambda user_id, force=False: force,          # Conditional cache bypass
    serializer=JsonSerializer(),
)
def get_user(user_id: int, force: bool = False) -> dict:
    return db.query_user(user_id)

# Async version: same decorator, auto-detects async function
@cached(conn, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)
```

### Cache protection strategies

| Strategy | Problem | Solution |
|----------|---------|----------|
| Penetration | Queries for non-existent data always hit DB | Cache null values with short TTL + BloomFilter pre-check |
| Breakdown | Hot key expires, concurrent requests flood DB | Distributed lock on cache miss (singleflight) |
| Avalanche | Many keys expire simultaneously | TTL randomization (jitter) + staggered expiration |

TTL jitter is built-in and on by default:

```python
cache = Cache(conn, ttl_jitter=0.1)  # +/- 10% random TTL variance
```

### Cache hooks (inspired by old codebase)

```python
class CacheHook(Protocol):
    def on_hit(self, key: str, latency_ms: float) -> None: ...
    def on_miss(self, key: str) -> None: ...
    def on_set(self, key: str, ttl: int | None) -> None: ...
    def on_delete(self, key: str) -> None: ...
    def on_error(self, key: str, error: Exception) -> None: ...
```

## 6. Lock Module

### Core API

Aligned with `threading.Lock` interface (inspired by Pottery).

```python
from redis_kit.lock import Lock, AsyncLock

lock = Lock(conn, prefix="myapp:lock")

# Basic usage — context manager
with lock("resource-1", timeout=10, blocking_timeout=5):
    do_critical_work()

# Async
async with AsyncLock(conn)("resource-1", timeout=10):
    await do_async_work()
```

### Features

**Reentrant lock**:
```python
with lock("resource", reentrant=True):
    with lock("resource", reentrant=True):  # Same thread/coroutine, no deadlock
        ...
```

**Read-write lock**:
```python
with lock.read("resource"):    # Multiple readers allowed
    data = read_shared_state()

with lock.write("resource"):   # Exclusive writer
    update_shared_state()
```

**Auto-renewal (watchdog)**:

Automatically extends lock TTL while the critical section is executing. Prevents lock expiration during long-running operations. Uses a background thread/task that renews at `timeout / 3` intervals.

```python
with lock("resource", timeout=30, auto_renew=True):
    do_long_running_work()  # Lock auto-extends every 10s
```

### Implementation

- Basic lock: Redis `SET NX EX` + Lua script for atomic release
- Reentrant: Thread/task ID tracking via Redis hash (holder + count)
- Read-write: Redis hash for reader count + exclusive writer flag, Lua scripts for atomicity
- Watchdog: `threading.Timer` (sync) / `asyncio.Task` (async) for periodic renewal

## 7. Queue Module

### PubSub

```python
from redis_kit.queue import PubSub, AsyncPubSub

pubsub = PubSub(conn, prefix="myapp:pubsub")

# Publish
pubsub.publish("events", {"type": "user_created", "id": 1})

# Subscribe
def handler(message):
    print(message)

pubsub.subscribe("events", handler)
pubsub.listen()  # Blocking loop

# Pattern subscribe
pubsub.psubscribe("events:*", handler)
```

PubSub automatically manages a dedicated connection (inspired by Lettuce), separate from command connections.

### Delay Queue

```python
from redis_kit.queue import DelayQueue, AsyncDelayQueue

dq = DelayQueue(conn, "order:timeout")

# Enqueue with delay
dq.put({"order_id": 123}, delay=1800)  # Execute after 30 minutes

# Poll for ready items
messages = dq.poll(count=10)
```

Implementation: Redis Sorted Set with score = execution timestamp.

### Reliable Queue

```python
from redis_kit.queue import ReliableQueue

rq = ReliableQueue(conn, "tasks")

# Producer
rq.put({"task": "send_email", "to": "user@example.com"})

# Consumer with acknowledgment
message = rq.get(timeout=5)
try:
    process(message.data)
    message.ack()
except Exception:
    message.nack()  # Return to queue
```

Implementation: Redis List + processing list (RPOPLPUSH pattern). Unacknowledged messages are returned to the queue after a configurable timeout.

## 8. Bloom Filter Module

```python
from redis_kit.bloom import BloomFilter, AsyncBloomFilter

bf = BloomFilter(conn, "user:emails", expected_items=100_000, false_positive_rate=0.01)

bf.add("alice@example.com")
bf.exists("alice@example.com")   # True
bf.exists("unknown@example.com") # False (probably)

# Batch operations
bf.add_many(["a@x.com", "b@x.com", "c@x.com"])
results = bf.exists_many(["a@x.com", "d@x.com"])  # [True, False]
```

Implementation: Multiple hash functions + Redis bit operations (SETBIT/GETBIT). Lua scripts for atomic multi-bit operations.

If Redis Stack (RedisBloom module) is available, auto-detect and delegate to `BF.ADD` / `BF.EXISTS` for better performance.

## 9. Counter & ID Generator Module

### Counter

API aligned with `collections.Counter` intuition (inspired by Pottery).

```python
from redis_kit.counter import Counter, AsyncCounter

counter = Counter(conn, prefix="myapp:counter")

# Basic operations
counter.incr("page_views")
counter.incr("page_views", 5)
counter.decr("page_views")
value = counter.get("page_views")

# Bound operations (inspired by Spring Data)
pv = counter.bind("page_views")
pv.incr()
pv.get()
pv.reset()
```

### ID Generator

```python
from redis_kit.counter import IDGenerator, AsyncIDGenerator

id_gen = IDGenerator(conn, "order_id")

new_id = id_gen.next()         # Atomic increment, returns int
new_id = id_gen.next_str()     # "000000001" — zero-padded string

# Prefixed IDs
id_gen = IDGenerator(conn, "order_id", prefix="ORD", padding=8)
new_id = id_gen.next_str()     # "ORD00000001"
```

Implementation: Redis `INCR` (atomic). IDGenerator is a thin wrapper over Counter with formatting logic.

## 10. Session Module

```python
from redis_kit.session import SessionManager, AsyncSessionManager

sessions = SessionManager(conn, prefix="session", ttl=1800)

# Create session
session_id = sessions.create({"user_id": 1, "role": "admin"})

# Read
data = sessions.get(session_id)

# Update (partial)
sessions.update(session_id, {"last_active": "2026-04-05T12:00:00"})

# Delete
sessions.delete(session_id)

# Refresh TTL (on activity)
sessions.refresh(session_id)
```

Implementation: Redis Hash per session. Session ID generated via `uuid4` by default, configurable generator.

## 11. Exception Handling

### Exception hierarchy

```python
class RedisKitError(Exception): ...

# Connection
class RedisConnectionError(RedisKitError): ...
class ConnectionPoolExhaustedError(RedisConnectionError): ...

# Serialization
class SerializationError(RedisKitError): ...

# Lock
class LockError(RedisKitError): ...
class LockAcquireError(LockError): ...
class LockReleaseError(LockError): ...

# Cache
class CacheError(RedisKitError): ...

# Queue
class QueueError(RedisKitError): ...
class QueueEmptyError(QueueError): ...

# Bloom
class BloomFilterError(RedisKitError): ...

# Session
class SessionError(RedisKitError): ...
class SessionNotFoundError(SessionError): ...
```

All exceptions wrap the original `redis.RedisError` with context (operation, key, module). Inspired by Spring Data's exception translation.

### Fallback policy

```python
from redis_kit.exceptions import FallbackPolicy

policy = FallbackPolicy(
    on_connection_error="return_none",   # "raise" | "return_none" | "callback"
    fallback=None,                       # Callable for "callback" mode
    log_on_fallback=True,                # Log when falling back (django-redis inspired)
    logger=None,                         # Custom logger, defaults to "redis_kit"
)

cache = Cache(conn, fallback_policy=policy)
```

Default: `raise` (fast-fail). User opts in to degradation.

## 12. Hooks & Observability

### CommandHook protocol

```python
class CommandHook(Protocol):
    def before(self, command: str, key: str, args: tuple) -> None: ...
    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None: ...
    def on_error(self, command: str, key: str, error: Exception) -> None: ...

class CompositeHook:
    """Chains multiple hooks. Inspired by old codebase's Composite pattern."""
    def __init__(self, *hooks: CommandHook): ...
```

### OpenTelemetry integration

Optional dependency: `pip install redis-kit[otel]`

```python
from redis_kit.observability import OpenTelemetryHook

hook = OpenTelemetryHook(service_name="myapp")
cache = Cache(conn, hooks=[hook])
```

Auto-creates spans for each Redis operation with attributes: command, key, duration, status.

### Metrics

```python
from redis_kit.observability import MetricsCollector

metrics = MetricsCollector()
cache = Cache(conn, hooks=[metrics])

# Access collected metrics
metrics.get_hit_rate("myapp:cache")
metrics.get_latency_percentiles("myapp:cache", p=[50, 95, 99])
```

## 13. Key Prefix System

Transparent key prefixing at module level (inspired by ioredis):

```python
cache = Cache(conn, prefix="myapp:cache")
cache.set("user:1", data)  # Actual Redis key: "myapp:cache:user:1"
cache.get("user:1")        # Automatically prefixed

lock = Lock(conn, prefix="myapp:lock")
with lock("resource"):     # Actual key: "myapp:lock:resource"
    ...
```

Prefix is applied transparently. Users never deal with full keys. Separator defaults to `:`, configurable via `NamespaceConfig`.

## 14. Sync/Async Strategy

Write both sync and async versions. Keep each module small so duplication is manageable.

Shared non-IO logic is extracted to `_logic.py` per module:
- Key building and prefix application
- Parameter validation
- Serialization/compression pipeline
- TTL parsing (string "2h30m" -> seconds)

IO code (the actual Redis calls) is in separate sync/async classes. Target < 150 lines per class.

```python
# Example structure for cache module
class _CacheLogic:
    """Pure logic: no IO, no async."""
    def _build_key(self, key: str) -> str: ...
    def _serialize(self, value: Any) -> bytes: ...
    def _deserialize(self, data: bytes) -> Any: ...
    def _parse_ttl(self, ttl: str | int | Callable) -> int: ...
    def _apply_jitter(self, ttl: int) -> int: ...

class Cache(_CacheLogic):
    def get(self, key: str) -> Any: ...       # Sync IO
    def set(self, key: str, value: Any, ttl=None) -> None: ...

class AsyncCache(_CacheLogic):
    async def get(self, key: str) -> Any: ... # Async IO
    async def set(self, key: str, value: Any, ttl=None) -> None: ...
```

## 15. Dependencies

### Required
- `redis >= 7.4.0`

### Optional (extras)
- `redis-kit[msgpack]` -> `msgpack`
- `redis-kit[lz4]` -> `lz4`
- `redis-kit[zstd]` -> `zstandard`
- `redis-kit[otel]` -> `opentelemetry-api`, `opentelemetry-sdk`
- `redis-kit[all]` -> all of the above

## 16. Public API (top-level exports)

```python
from redis_kit import (
    # Connection
    ConnectionManager,
    ConnectionConfig,

    # Cache
    Cache, AsyncCache, cached,

    # Lock
    Lock, AsyncLock,

    # Queue
    PubSub, AsyncPubSub,
    DelayQueue, AsyncDelayQueue,
    ReliableQueue, AsyncReliableQueue,

    # Bloom
    BloomFilter, AsyncBloomFilter,

    # Counter
    Counter, AsyncCounter,
    IDGenerator, AsyncIDGenerator,

    # Session
    SessionManager, AsyncSessionManager,

    # Serializers
    JsonSerializer, MsgpackSerializer, PickleSerializer,

    # Compressors
    ZstdCompressor, Lz4Compressor, ZlibCompressor,

    # Exceptions
    RedisKitError, FallbackPolicy,
)
```

## 17. What is NOT in v1

- Sentinel / Cluster topology support (v2)
- Repository pattern (versioning, audit, soft-delete)
- Rate limiter (token bucket, sliding window)
- Autopipelining
- Multi-level cache (local + Redis)
- Hash ring / sharding
- Redis Streams consumer groups

## 18. Design References

| Source | What we borrowed |
|--------|-----------------|
| Pottery | API aligned with Python stdlib (Lock ~ threading.Lock, Counter ~ collections.Counter) |
| cashews | TTL string format "2h30m", multiple cache strategies |
| aiocache | Backend/Serializer/Plugin three-layer separation |
| django-redis | Compressor as independent layer, TTL operations, SCAN-based iteration |
| Spring Data Redis | Bound operations (.bind(key)), exception translation layer |
| Lettuce | sync/async views on connection |
| ioredis | Transparent key prefixing |
| BadrElfarri/rediskit | Callable key/TTL/bypass in decorators |
| Old codebase | CacheHook design, Event Loop isolation, frozen configs |
