# redis-py-kit

Enterprise-grade Python Redis toolkit with sync/async dual-mode APIs.

[![PyPI](https://img.shields.io/pypi/v/redis-py-kit.svg)](https://pypi.org/project/redis-py-kit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## Features

- **Cache** — Get/Set/Delete, TTL management, batch operations, SCAN-based iteration, `@cached` decorator, BoundCache, TTL jitter (anti-avalanche), None caching (anti-penetration)
- **Distributed Lock** — Basic lock, reentrant lock, read-write lock, watchdog auto-renewal, Lua-scripted atomic operations
- **Queue** — PubSub, DelayQueue (Sorted Set), ReliableQueue (LMOVE + ack/nack)
- **Bloom Filter** — SHA-256 multi-hash, pipeline-based bit operations, configurable false positive rate
- **Counter & ID Generator** — Atomic INCR/DECR, BoundCounter, zero-padded ID generation
- **Session Manager** — Redis Hash per session, CRUD, TTL refresh, custom ID generator
- **Observability** — MetricsCollector hook, OpenTelemetry integration (optional)
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
@cached(conn.sync_client, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)
```

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

# Read-write lock
with lock.read("resource"):
    data = read_shared_state()

with lock.write("resource"):
    update_shared_state()
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

# PubSub
pubsub = PubSub(conn.sync_client, prefix="myapp")
pubsub.publish("events", {"type": "user_created", "id": 1})
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
data = sessions.get(session_id)
sessions.update(session_id, {"last_active": "2026-04-09"})
sessions.refresh(session_id)  # Reset TTL
sessions.delete(session_id)
```

### Observability

```python
from redis_kit import Cache, MetricsCollector

metrics = MetricsCollector()
cache = Cache(conn.sync_client, prefix="myapp", hooks=[metrics])

# After some operations...
metrics.command_count("GET")
metrics.error_count()
metrics.latency_stats()  # {"count": N, "avg": X, "min": Y, "max": Z}

# OpenTelemetry (requires redis-kit[otel])
from redis_kit.observability import OpenTelemetryHook

hook = OpenTelemetryHook(service_name="myapp")
cache = Cache(conn.sync_client, hooks=[hook])
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

## Exception Handling

```python
from redis_kit import RedisKitError, FallbackPolicy

# Configurable degradation
policy = FallbackPolicy(
    on_connection_error="return_none",  # "raise" | "return_none" | "callback"
    log_on_fallback=True,
)
cache = Cache(conn.sync_client, fallback_policy=policy)
```

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
└── SessionError
    └── SessionNotFoundError
```

## Requirements

- Python >= 3.11
- Redis >= 7.0
- redis-py >= 7.4.0

## License

MIT
