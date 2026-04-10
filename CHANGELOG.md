# Changelog

## [0.7.0] - 2026-04-10

### Fixed (Critical)
- **Lock**: Read/write lock now fully atomic via Lua scripts, fixing race condition in `write()` (C1)
- **Lock**: Lua scripts declare all accessed keys in `KEYS[]` for Redis Cluster compliance (C2)
- **Lock**: Watchdog timer chain properly tracked and cancelled on release (C4)
- **Cache**: `remember()` now correctly caches `None` values from factory (C3)
- **Repository**: Optimistic lock is now atomic check-and-write in single Lua script (C5)
- **PubSub**: Pattern subscription (`psubscribe`) handler lookup fixed — uses `message["pattern"]` (C6)
- **Stream**: Added `StreamMessage.async_ack()` for async consumer manual ACK (C7)
- **Queue**: `ReliableQueue._nack()` is now atomic via Lua, preserves original msg_id (C8)
- **Session**: `create()` uses pipeline for atomic hset+expire (C9)
- **Connection**: `ClusterConfig.read_from_replicas` now passed to RedisCluster (C10)

### Fixed (Important)
- **Cache**: `apply_jitter` clamped to min=1, preventing TTL=0 errors
- **Cache**: `@cached` decorator guards against TTL=0 with fallback to `SET`
- **Cache**: `AsyncCache` now has full hook support (parity with sync `Cache`)
- **Cache**: `delete_pattern` uses batch `DELETE` instead of per-key calls
- **Cache**: `TieredCache.get_many()` applies negative caching for L2 misses
- **Cache**: Unified `_MISS` sentinel across `_logic.py` and `local.py`
- **Observability**: `MetricsCollector` is now thread-safe with bounded `deque`
- **Observability**: `OpenTelemetryHook` creates spans in `before()`, ends in `after()`/`on_error()`
- **Hooks**: `CompositeHook` isolates exceptions per hook (one failure doesn't block others)
- **Connection**: `ssl` config now passed in `from_url` path
- **Connection**: `assert isinstance` replaced with `raise TypeError` (survives `python -O`)
- **Config**: `SentinelConfig.sentinels` / `ClusterConfig.startup_nodes` now immutable `tuple`
- **Repository**: `_from_hash` uses `typing.get_type_hints()` for robust type resolution
- **Repository**: Soft delete now bumps `version` and `updated_at`
- **Queue**: `DelayQueue.put()` uses unique member IDs to prevent deduplication
- **PubSub**: Per-message error isolation in `listen()` loop
- **RateLimit**: `TokenBucketLimiter` validates `rate > 0` and `capacity > 0`
- **Session**: `update()` uses pipeline to fix TOCTOU race, refreshes TTL
- **Bloom**: Added `reset()` method
- **Exports**: All 20 exceptions now exported from top-level `__init__.py`

### Improved (Suggestions)
- **Cache**: Removed dead `group_keys_by_slot` code from `_cluster.py`
- **Cache**: `Cache.set()` hook now measures actual duration instead of hardcoded 0
- **Cache**: `LRUCache.size` property is now thread-safe
- **Cache**: `TieredCache` / `AsyncTieredCache` now support `bind()` method
- **Cache**: `@cached` decorator supports `.invalidate()` for cache entry removal
- **Bloom**: Switched from SHA-256 to double hashing (MD5-based, ~3.5x faster)
- **Bloom**: `exists_many` uses single pipeline instead of N round trips
- **Repository**: `find_all()` uses pipeline instead of N+1 queries
- **Repository**: `restore()` on non-deleted entity now raises `RepositoryError` (not `EntityNotFoundError`)
- **Session**: Values serialized with JSON (preserves types) instead of `str()`
- **Counter**: `decr()` docstring documents that values can go below zero
- **Queue**: `DelayQueue` Lua poll script extracted to shared `queue/_lua.py`
- 13 new async tests (ratelimit, reliable queue ack/nack, stream pending)

### Stats
- 336 tests (up from 299), 0 failures
- 42 files changed, +906 -143 lines

## [0.6.1] - 2026-04-10

### Improved
- Async unit tests for all modules — coverage 73% → 82%
- Integration tests with real Redis (Standalone 15 + Sentinel 3 + Cluster 4)
- docker-compose for local testing (Standalone + Sentinel + Cluster)
- CI: separate integration test jobs for each topology
- Added pytest-cov to dev dependencies

## [0.6.0] - 2026-04-10

### Added
- **Repository** module — structured entity storage with enterprise features:
  - `BaseModel` — dataclass base with audit metadata (id, version, created_at, updated_at, deleted, deleted_at)
  - `Repository` / `AsyncRepository` — full CRUD with Redis Hash storage
  - **Optimistic locking** — Lua-scripted version check, `OptimisticLockError` on conflict
  - **Soft delete** — `delete()` marks as deleted, `restore()` recovers, `hard_delete()` removes permanently
  - **Audit fields** — `created_at`/`updated_at` auto-populated on save
  - **Version history** — `get_history()` returns all previous versions (Redis List)
  - `find_all()`, `find_including_deleted()` for querying
  - `RepositoryError`, `EntityNotFoundError`, `OptimisticLockError` exceptions
- 22 new tests (266 total)

## [0.5.0] - 2026-04-10

### Added
- **Redis Streams** module — consumer group abstraction replacing ReliableQueue:
  - `StreamProducer` / `AsyncStreamProducer` — XADD, XLEN, XTRIM
  - `StreamConsumer` / `AsyncStreamConsumer` — XREADGROUP with auto/manual ACK, consumer group management
  - `StreamMessage` — message dataclass with `.ack()` support
  - `ensure_group()` — idempotent consumer group creation (XGROUP CREATE)
  - `claim_stale()` — dead letter handling via XAUTOCLAIM
  - `pending()` — view unacknowledged messages via XPENDING
  - `StreamError` exception
- 14 new tests (244 total)

## [0.4.0] - 2026-04-10

### Added
- **Tiered Cache** module — L1 (local LRU) + L2 (Redis) two-tier cache:
  - `LRUCache` — thread-safe, per-entry TTL, LRU eviction, zero dependencies
  - `TieredCache` / `AsyncTieredCache` — transparent L1→L2 read-through with backfill
  - Negative caching — short-TTL `_NEGATIVE` marker prevents repeated L2 miss penetration
  - `get_many` optimization — batch L1 lookup, only missed keys go to L2
  - Write-through — `set`/`set_many` write both L1 and L2
  - `invalidate_local()` / `clear_local()` / `local_size` for local cache management
- 30 new tests (230 total)

## [0.3.0] - 2026-04-10

### Added
- **Rate Limiter** module with two algorithms:
  - `TokenBucketLimiter` / `AsyncTokenBucketLimiter` — smooth traffic with burst tolerance, Lua-scripted atomic operations
  - `SlidingWindowLimiter` / `AsyncSlidingWindowLimiter` — exact counting with Redis Sorted Set + Lua script
- `@rate_limit` decorator with DSL parsing (e.g. `"100/minute"`)
- `RateLimitResult` dataclass (allowed, limit, remaining, retry_after, reset_at) — maps to HTTP rate limit headers
- `RateLimitExceeded` exception with result context
- 30 new tests (200 total)

## [0.2.0] - 2026-04-10

### Added
- **Sentinel support**: `SentinelConfig` — automatic failover, upstream modules unaware
- **Cluster support**: `ClusterConfig` — data sharding, multi-key operations auto-degrade
- `ConnectionManager.topology`, `.is_cluster`, `.is_sentinel` properties
- `Cache`/`AsyncCache` `is_cluster` parameter — `get_many`/`set_many` auto-degrade to individual operations
- `Lock`/`AsyncLock` `is_cluster` parameter — keys wrapped in `{hash_tag}` for Lua script slot safety
- `TopologyConstraintError` exception
- `group_keys_by_slot()` utility for Cluster multi-key operations
- 22 new tests (170 total)

## [0.1.1] - 2026-04-10

### Fixed
- R/W lock now uses Lua scripts for atomic read-acquire/release operations
- `ReliableQueue._ack()` uses direct `lrem` with raw payload instead of O(N) scan
- `BloomFilter` and `IDGenerator` now accept configurable key prefix (default unchanged)

## [0.1.0] - 2026-04-09

### Added
- **Cache** module: `Cache`, `AsyncCache`, `BoundCache`, `@cached` decorator
  - TTL string format parsing ("2h30m")
  - TTL jitter for avalanche protection
  - Batch operations (`get_many`, `set_many`)
  - SCAN-based pattern operations (`delete_pattern`, `iter_keys`)
  - Cache-aside pattern (`remember`)
  - None value caching (anti-penetration)
- **Lock** module: `Lock`, `AsyncLock`
  - Basic distributed lock (SET NX EX + Lua release)
  - Reentrant lock (Hash-based owner + count)
  - Read-write lock
  - Watchdog auto-renewal
- **Queue** module: `PubSub`, `AsyncPubSub`, `DelayQueue`, `AsyncDelayQueue`, `ReliableQueue`, `AsyncReliableQueue`
  - DelayQueue via Sorted Set + Lua poll
  - ReliableQueue via LMOVE + ack/nack
- **BloomFilter** module: `BloomFilter`, `AsyncBloomFilter`
  - SHA-256 multi-hash, pipeline-based bit operations
- **Counter** module: `Counter`, `AsyncCounter`, `IDGenerator`, `AsyncIDGenerator`
  - BoundCounter for single-key operations
  - Zero-padded ID generation
- **Session** module: `SessionManager`, `AsyncSessionManager`
  - Redis Hash per session, CRUD, TTL refresh
- **Observability**: `MetricsCollector`, `OpenTelemetryHook` (optional)
- **Serializers**: `JsonSerializer`, `PickleSerializer`, `MsgpackSerializer` (optional)
- **Compressors**: `ZlibCompressor`, `ZstdCompressor` (optional), `Lz4Compressor` (optional)
- **ConnectionManager**: Sync/async views, lazy init, event loop isolation
- **Exception hierarchy**: `RedisKitError` base + module-specific exceptions
- **FallbackPolicy**: Configurable degradation ("raise" / "return_none" / "callback")
- **CommandHook** protocol + `CompositeHook` for extensible observability
