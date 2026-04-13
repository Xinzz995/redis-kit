# redis-py-kit

Enterprise-grade Python Redis toolkit with sync/async dual-mode APIs.

[![PyPI](https://img.shields.io/pypi/v/redis-py-kit.svg)](https://pypi.org/project/redis-py-kit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-中文%20%7C%20English-blue.svg)](https://xinzz995.github.io/redis-kit/)
[![Status](https://img.shields.io/badge/status-Production%2FStable-brightgreen.svg)](https://pypi.org/project/redis-py-kit/)

> **[中文文档](https://xinzz995.github.io/redis-kit/)** | **[English Docs](https://xinzz995.github.io/redis-kit/en/)**

## Features

- **Cache** — Get/Set/Delete, TTL management, batch operations, SCAN-based iteration, `@cached` decorator with `.invalidate()` and `on_error` degradation, BoundCache, TTL jitter (anti-avalanche), None caching (anti-penetration), FallbackPolicy degradation (raise/return_none/callback), full hook lifecycle (before/after/error)
- **Distributed Lock** — Basic lock, reentrant lock, read-write lock (with `blocking_timeout` and `auto_renew`), watchdog auto-renewal, Lua-scripted atomic operations, exception-safe context manager
- **Queue** — PubSub (with graceful `stop()` and `listen(timeout=)`), DelayQueue (Sorted Set), ReliableQueue (LMOVE + ack/nack + `recover_stale()`)
- **Bloom Filter** — Double hashing (SHA-256), pipeline-based bit operations, configurable false positive rate, `reset()`
- **Counter & ID Generator** — Atomic INCR/DECR, BoundCounter, zero-padded ID generation
- **Session Manager** — Redis Hash per session, JSON serialization (type-preserving), CRUD, TTL refresh, custom ID generator
- **Rate Limiter** — Token bucket (burst-tolerant) and sliding window (exact count), Lua-scripted with server-side `TIME`, `@rate_limit` decorator
- **Tiered Cache** — L1 local LRU + L2 Redis, read-through backfill, negative caching, `bind()`, zero dependencies
- **Redis Streams** — Consumer groups with auto/manual ACK, `async_ack()` for async consumers, dead letter recovery (XAUTOCLAIM)
- **Repository** — Dataclass entity → Redis Hash, CRUD, optimistic locking, soft delete, audit fields, version history
- **Observability** — Thread-safe MetricsCollector hook, OpenTelemetry integration with proper span lifecycle (optional)
- **Pluggable Serialization** — JSON (default), Pickle, MessagePack (optional)
- **Pluggable Compression** — Zlib, Zstandard (optional), LZ4 (optional)
- **Topology Support** — Standalone, Sentinel (auto-failover), Cluster (data sharding) — switch by config
- **Sync + Async** — Every module provides both sync and async APIs

## Installation

```bash
pip install redis-py-kit
```

With optional extras:

```bash
pip install redis-py-kit[msgpack]     # MessagePack serializer
pip install redis-py-kit[zstd]        # Zstandard compressor
pip install redis-py-kit[lz4]         # LZ4 compressor
pip install redis-py-kit[otel]        # OpenTelemetry integration
pip install redis-py-kit[all]         # All optional dependencies
```

## Quick Start

### Cache

```python
from redis_kit import ConnectionManager, Cache, cached

conn = ConnectionManager(url="redis://localhost:6379/0")

# Basic cache operations
cache = Cache(conn.sync_client, prefix="myapp:cache")
cache.set("user:1", {"name": "Alice"}, ttl="2h30m")
user = cache.get("user:1")

# Cache-aside pattern
user = cache.remember("user:1", factory=load_user_from_db, ttl=3600)

# Batch operations
cache.set_many({"a": 1, "b": 2, "c": 3}, ttl=3600)
values = cache.get_many(["a", "b", "c"])

# Bound operations
user_cache = cache.bind("user:1")
user_cache.set({"name": "Alice"}, ttl=3600)
user_cache.get()
user_cache.ttl()

# Decorator
@cached(conn.sync_client, key="user:{user_id}", ttl="1h")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# Async decorator (auto-detected)
@cached(conn.async_client, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)

# Cache invalidation
get_user.invalidate(user_id=1)
await get_product.invalidate(pid=42)

# Graceful degradation — skip cache on Redis failure
@cached(conn.sync_client, key="user:{user_id}", ttl="1h", on_error="execute")
def get_user_safe(user_id: int) -> dict:
    return db.query_user(user_id)
```

TTL strings must be fully valid. Inputs like `"1hfoo"` raise `ValueError` instead of being partially parsed.

### Distributed Lock

```python
from redis_kit import Lock, AsyncLock

lock = Lock(conn.sync_client, prefix="myapp:lock")

# Basic lock
with lock("resource-1", timeout=10):
    do_critical_work()

# Reentrant lock
with lock("resource", timeout=10, reentrant=True):
    with lock("resource", timeout=10, reentrant=True):
        ...  # No deadlock

# Watchdog auto-renewal
with lock("resource", timeout=30, auto_renew=True):
    do_long_running_work()  # Lock auto-extends every 10s

# Read-write lock (with optional blocking_timeout for reads)
with lock.read("resource", blocking_timeout=5.0):
    data = read_shared_state()

with lock.write("resource", auto_renew=True):
    update_shared_state()  # Writer lock auto-extends

# Exception-safe: all context managers (lock, read, write) never mask your exception
try:
    with lock("resource", timeout=5):
        raise ValueError("business error")
except ValueError:
    pass  # ValueError propagates even if lock release fails

try:
    with lock.write("resource", timeout=5):
        raise ValueError("write error")
except ValueError:
    pass  # Same guarantee for read-write locks
```

### Queue

```python
from redis_kit import DelayQueue, ReliableQueue, PubSub

# Delay queue
dq = DelayQueue(conn.sync_client, "order:timeout")
dq.put({"order_id": 123}, delay=1800)  # Execute in 30 minutes
messages = dq.poll(count=10)

# Reliable queue with ack/nack
rq = ReliableQueue(conn.sync_client, "tasks")
rq.put({"task": "send_email", "to": "user@example.com"})

msg = rq.get(timeout=5)
try:
    process(msg.data)
    msg.ack()
except Exception:
    msg.nack()  # Return to queue

# Recover messages from crashed consumers
recovered = rq.recover_stale(max_items=100)

# PubSub
pubsub = PubSub(conn.sync_client, prefix="myapp")
pubsub.publish("events", {"type": "user_created", "id": 1})

def handler(msg):
    print(msg)

pubsub.subscribe("events", handler)
pubsub.psubscribe("events.*", handler)  # Pattern subscription

# Run in background thread with graceful shutdown
import threading
thread = threading.Thread(target=pubsub.listen, kwargs={"timeout": 1.0})
thread.start()

pubsub.stop()    # Signal listen() to exit
thread.join()
```

### Bloom Filter

```python
from redis_kit import BloomFilter

bf = BloomFilter(conn.sync_client, "emails", expected_items=100_000, false_positive_rate=0.01)

bf.add("alice@example.com")
bf.exists("alice@example.com")   # True
bf.exists("unknown@example.com") # False (probably)

bf.add_many(["a@x.com", "b@x.com"])
results = bf.exists_many(["a@x.com", "c@x.com"])  # [True, False]

bf.reset()  # Clear the filter
```

### Counter & ID Generator

```python
from redis_kit import Counter, IDGenerator

counter = Counter(conn.sync_client, prefix="myapp:counter")
counter.incr("page_views")
counter.incr("page_views", 5)
value = counter.get("page_views")

# Bound counter
pv = counter.bind("page_views")
pv.incr()
pv.get()

# ID generator
id_gen = IDGenerator(conn.sync_client, "order_id", prefix="ORD", padding=8)
new_id = id_gen.next_str()  # "ORD00000001"
```

### Session Manager

```python
from redis_kit import SessionManager

sessions = SessionManager(conn.sync_client, prefix="session", ttl=1800)

session_id = sessions.create({"user_id": 1, "role": "admin"})
data = sessions.get(session_id)  # {"user_id": 1, "role": "admin"} — types preserved
sessions.update(session_id, {"last_active": "2026-04-09"})  # Also refreshes TTL
sessions.refresh(session_id)  # Reset TTL
sessions.delete(session_id)
```

### Observability

```python
from redis_kit import Cache, MetricsCollector, CommandHook

metrics = MetricsCollector()
cache = Cache(conn.sync_client, prefix="myapp", hooks=[metrics])

# After some operations...
metrics.command_count("GET")
metrics.error_count()              # Total errors
metrics.error_count(command="GET") # Errors for specific command
metrics.latency_stats()  # {"count": N, "avg": X, "min": Y, "max": Z}

# OpenTelemetry (requires redis-kit[otel])
from redis_kit.observability import OpenTelemetryHook

hook = OpenTelemetryHook(service_name="myapp")
cache = Cache(conn.sync_client, hooks=[hook])

# Custom hook — implement the CommandHook protocol
class LoggingHook(CommandHook):
    def before(self, command, key, args): print(f"→ {command} {key}")
    def after(self, command, key, result, duration_ms): print(f"← {command} {key} ({duration_ms:.1f}ms)")
    def on_error(self, command, key, error): print(f"✗ {command} {key}: {error}")
```

### Rate Limiter

```python
from redis_kit import TokenBucketLimiter, SlidingWindowLimiter, rate_limit

# Token bucket — smooth traffic, allow bursts
limiter = TokenBucketLimiter(conn.sync_client, rate=10, capacity=50)
result = limiter.acquire("user:123")
# result.allowed, result.remaining, result.retry_after, result.reset_at

# Sliding window — strict counting
limiter = SlidingWindowLimiter(conn.sync_client, limit=100, window=60)
result = limiter.acquire("user:123")

if not result.allowed:
    print(f"Rate limited, retry after {result.retry_after:.1f}s")

# Decorator with DSL
@rate_limit(conn.sync_client, key="api:{user_id}", limit="100/minute")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# Async — pass async client for async functions
@rate_limit(conn.async_client, key="api:{uid}", limit="10/second", algorithm="token_bucket")
async def get_product(uid: int) -> dict:
    return await db.query_product(uid)
```

The DSL must match completely, and `algorithm` must be either `"sliding_window"` or `"token_bucket"`. Invalid values raise `ValueError`.

### Tiered Cache

```python
from redis_kit import Cache
from redis_kit.cache import TieredCache

redis_cache = Cache(conn.sync_client, prefix="myapp:cache")

# Wrap with local LRU layer
cache = TieredCache(
    redis_cache,
    local_maxsize=2000,   # L1: max 2000 entries
    local_ttl=30.0,       # L1: 30s TTL
    negative_ttl=5.0,     # Cache misses for 5s (anti-penetration)
)

cache.set("user:1", data, ttl=3600)   # Write-through: L1 + L2
user = cache.get("user:1")             # L1 hit — skip Redis
user = cache.get("nonexistent")        # L1 miss → L2 miss → negative cached

# Batch: L1 first, only misses go to L2
data = cache.get_many(["user:1", "user:2", "user:3"])

# Local cache management
cache.invalidate_local("user:1")
cache.clear_local()
print(f"Local entries: {cache.local_size}")
```

### Redis Streams

```python
from redis_kit import StreamProducer, StreamConsumer

# Producer
producer = StreamProducer(conn.sync_client, stream="orders", maxlen=10000)
producer.add({"order_id": "123", "status": "created"})

# Consumer — auto ACK
consumer = StreamConsumer(
    conn.sync_client, stream="orders",
    group="processor", consumer_name="worker-1",
    auto_ack=True,
)
consumer.ensure_group()

for message in consumer.listen(count=10, block=5000):
    process(message.data)  # Auto-ACK after iteration

# Manual ACK mode
consumer = StreamConsumer(
    conn.sync_client, stream="orders",
    group="processor", consumer_name="worker-2",
    auto_ack=False,
)
consumer.ensure_group()

for message in consumer.listen(count=10, block=5000):
    try:
        process(message.data)
        message.ack()
    except Exception:
        pass  # Recover via claim_stale later

# Dead letter recovery
stale = consumer.claim_stale(min_idle_ms=60000, count=10)
for msg in stale:
    handle_dead_letter(msg)
    msg.ack()
```

### Repository

```python
from dataclasses import dataclass
from redis_kit import Repository, BaseModel

@dataclass
class AppConfig(BaseModel):
    name: str = ""
    value: str = ""
    env: str = "production"

repo = Repository(conn.sync_client, AppConfig, prefix="config")

# Create — auto ID, version=1, created_at
config = repo.save(AppConfig(name="max_retries", value="3"))

# Read
found = repo.find(config.id)

# Update — optimistic lock, auto version increment
found.value = "5"
updated = repo.save(found)  # version 1→2, updated_at auto

# Concurrent conflict detection
stale = repo.find(config.id)
updated.value = "10"
repo.save(updated)        # OK (version 2→3)
stale.value = "20"
repo.save(stale)           # OptimisticLockError!

# Soft delete + restore (both use optimistic locking, auto version increment)
repo.delete(config.id)              # deleted=True, version+1
repo.find(config.id)                # None
repo.find_including_deleted(config.id)  # Still accessible
repo.restore(config.id)             # Recovered, version+1

# Version history
history = repo.get_history(config.id)  # previous states from save(), delete(), and restore()

# Hard delete (permanent)
repo.hard_delete(config.id)
```

### Async Usage

Every module has an async counterpart:

```python
from redis_kit import AsyncCache, AsyncLock, AsyncSessionManager

cache = AsyncCache(conn.async_client, prefix="myapp:cache")
await cache.set("key", "value", ttl=3600)
value = await cache.get("key")

async with AsyncLock(conn.async_client, prefix="lock")("resource", timeout=10):
    await do_async_work()
```

## Topology Support

Switch between Standalone, Sentinel, and Cluster by changing the Config object — all downstream modules work unchanged.

### Standalone (default)

```python
from redis_kit import ConnectionManager, ConnectionConfig

conn = ConnectionManager(config=ConnectionConfig(host="localhost", port=6379))
# or simply
conn = ConnectionManager(url="redis://localhost:6379/0")
```

> **Note:** The `url` parameter is only supported with `ConnectionConfig` (standalone mode). Passing `url` with `SentinelConfig` or `ClusterConfig` raises `ValueError`.

### Sentinel

```python
from redis_kit import ConnectionManager, SentinelConfig, Cache

conn = ConnectionManager(config=SentinelConfig(
    sentinels=[("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)],
    service_name="mymaster",
    password="secret",
))

# Downstream usage unchanged — Sentinel handles failover transparently
cache = Cache(conn.sync_client, prefix="myapp:cache")
```

### Cluster

```python
from redis_kit import ConnectionManager, ClusterConfig, Cache, Lock

conn = ConnectionManager(config=ClusterConfig(
    startup_nodes=[("node1", 6379), ("node2", 6379), ("node3", 6379)],
    password="secret",
    read_from_replicas=True,
))

# Pass is_cluster for modules that need Cluster adaptation
cache = Cache(conn.sync_client, prefix="myapp:cache", is_cluster=conn.is_cluster)
lock = Lock(conn.sync_client, prefix="myapp:lock", is_cluster=conn.is_cluster)
```

**Cluster adaptations (automatic):**
- `get_many` / `set_many` — degrade to individual operations (no cross-slot MGET/MSET)
- Lock keys wrapped in `{hash_tag}` — Lua scripts stay on one slot
- `delete_pattern` / `iter_keys` — `scan_iter` works across all Cluster nodes

## Serialization & Compression

```python
from redis_kit import Cache, JsonSerializer, PickleSerializer
from redis_kit.serializers import MsgpackSerializer  # requires redis-kit[msgpack]
from redis_kit import ZlibCompressor
from redis_kit.compressors import ZstdCompressor      # requires redis-kit[zstd]

# Combine any serializer with any compressor
cache = Cache(
    conn.sync_client,
    prefix="myapp",
    serializer=MsgpackSerializer(),
    compressor=ZstdCompressor(),
)
```

### Custom Implementations

Implement the `Serializer` or `Compressor` protocol:

```python
from redis_kit import Serializer, Compressor

class MySerializer(Serializer):
    def dumps(self, value: object) -> bytes: ...
    def loads(self, data: bytes) -> object: ...

class MyCompressor(Compressor):
    def compress(self, data: bytes) -> bytes: ...
    def decompress(self, data: bytes) -> bytes: ...
```

## Exception Handling

```python
from redis_kit import RedisKitError, FallbackPolicy, Cache

# Strategy 1: Silent degradation — return None on connection failure
policy = FallbackPolicy(on_connection_error="return_none")
cache = Cache(conn.sync_client, fallback_policy=policy)

# Strategy 2: Custom callback — fall back to local cache
def local_fallback(command, key, error):
    return local_cache.get(key) if command == "GET" else None

policy = FallbackPolicy(on_connection_error="callback", fallback=local_fallback)
cache = Cache(conn.sync_client, fallback_policy=policy)
```

Only triggers for `RedisConnectionError` and `RedisTimeoutError`. Other exceptions always re-raise. Serialization failures raise `SerializationError` with the original error chained.

Exception hierarchy:

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

## Requirements

- Python >= 3.11
- Redis >= 7.0
- redis-py >= 7.4.0

## License

MIT
