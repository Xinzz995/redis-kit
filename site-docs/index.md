# redis-py-kit

**Enterprise-grade Python Redis toolkit with sync/async dual-mode APIs.**

[![PyPI](https://img.shields.io/pypi/v/redis-py-kit.svg)](https://pypi.org/project/redis-py-kit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## Features

| Module | Description |
|--------|-------------|
| [Cache](modules/cache.md) | Get/Set/Delete, TTL, batch ops, `@cached` decorator, TTL jitter |
| [Tiered Cache](modules/tiered-cache.md) | L1 local LRU + L2 Redis, read-through, negative caching |
| [Lock](modules/lock.md) | Basic, reentrant, read-write, watchdog auto-renewal |
| [Queue](modules/queue.md) | PubSub, DelayQueue, ReliableQueue |
| [Streams](modules/streams.md) | Consumer groups, auto/manual ACK, dead letter recovery |
| [Bloom Filter](modules/bloom.md) | SHA-256 multi-hash, pipeline bit operations |
| [Counter](modules/counter.md) | Atomic INCR/DECR, BoundCounter, ID Generator |
| [Session](modules/session.md) | Redis Hash sessions, CRUD, TTL refresh |
| [Rate Limiter](modules/ratelimit.md) | Token bucket, sliding window, `@rate_limit` decorator |
| [Repository](modules/repository.md) | Dataclass entities, versioning, soft delete, audit, history |
| [Observability](modules/observability.md) | MetricsCollector, OpenTelemetry hooks |

## Quick Install

```bash
pip install redis-py-kit
```

## Quick Example

```python
from redis_kit import ConnectionManager, Cache

conn = ConnectionManager(url="redis://localhost:6379/0")
cache = Cache(conn.sync_client, prefix="myapp:cache")

cache.set("user:1", {"name": "Alice"}, ttl="2h30m")
user = cache.get("user:1")
```
