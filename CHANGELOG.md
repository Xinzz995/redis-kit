# Changelog

## [0.7.2] - 2026-04-11

### Fixed
- **Cache**: `parse_ttl()` now rejects negative TTL values with `ValueError` — previously silently created permanent keys
- **Cache**: `_notify_hooks()` wraps each hook call in `try/except` — a misbehaving hook no longer breaks cache operations (matches `CompositeHook` pattern)
- **Cache**: `TieredCache.get_many()` now correctly distinguishes cached `None` from cache miss — previously wrote `_NEGATIVE` to L1 for cached `None` values
- **Cache**: `AsyncTieredCache` gained `iter_keys()` method — restores sync/async API parity
- **Connection**: `ConnectionManager.close()` now acquires `_sync_lock` — fixes race condition with concurrent `sync_client` access
- **Exceptions**: `FallbackPolicy(on_connection_error="callback")` now validates that `fallback` is not `None` at construction time
- **Lock**: `read()` and `write()` context managers switched from `try/finally` to `except/else` — release failures no longer mask the original exception (matches `__call__` behavior)
- **PubSub**: `AsyncPubSub.listen()` now detects and `await`s async handlers — previously silently discarded unawaited coroutines
- **Queue**: `DelayQueue.put()` and `poll()` now use Redis server-side `TIME` via Lua scripts — eliminates distributed clock drift (matches RateLimit approach)
- **Repository**: `restore()` now uses optimistic locking, increments `version`, and updates `updated_at` — previously skipped version check and broke the mutation invariant

### Removed
- Dead file `redis_kit/cache/_cluster.py` (empty, never imported)
- Dead function `resolve_callable()` in `redis_kit/cache/_logic.py` (never used)
- Dead code branch in `Repository._from_hash()` datetime handling (`raw != "__NONE__"` always true)

### Stats
- 430 tests (up from 414), 0 failures
- 24 files changed, +400 -68 lines

## [0.7.1] - 2026-04-11

### Fixed (Critical)
- **Repository**: `save()` history lpush moved after optimistic lock check — prevents history pollution on version conflict (C-1)
- **PubSub**: `except Exception: pass` replaced with `_logger.exception()` — errors are now logged instead of silently swallowed (C-2)
- **RateLimit**: `@rate_limit` decorator type hint updated to accept both sync and async Redis clients (C-3)
- **Cache**: `hooks.before()` and `hooks.on_error()` now called for all operations — previously dead code (C-4)
- **Cache**: `FallbackPolicy` fully implemented — three strategies: `"raise"`, `"return_none"`, `"callback"` (C-5)
- **OTel**: `ContextVar` replaced with span stack (`ContextVar[list[Span]]`) — fixes concurrent async span leak (C-6)

### Fixed (Important)
- **Repository**: `_from_hash` now handles `dataclasses.MISSING` default fields without crashing (I-1)
- **Repository**: `get_type_hints` catches `(NameError, AttributeError)` instead of broad `Exception` (I-2)
- **Repository**: `datetime.now()` replaced with `datetime.now(tz=UTC)` for timezone safety (I-3)
- **Session**: `update()` now uses Lua script for atomic EXISTS+HSET+EXPIRE (I-4)
- **Session**: `refresh()` simplified to single `expire()` call, eliminating TOCTOU race (I-5)
- **Stream**: `ensure_group()` catches `ResponseError` instead of broad `Exception` for BUSYGROUP (I-6)
- **TieredCache**: `get()` uses `_get_raw()` to distinguish cached `None` from cache miss (I-7)
- **Lock**: Watchdog timer list pruned in `renew()` to prevent memory leak (I-8)
- **Repository**: `delete()` now uses Lua optimistic lock — prevents concurrent version conflicts (I-9)

### Improved (Suggestions)
- **RateLimit**: Lua scripts now use `redis.call("TIME")` instead of client-side `time.time()` — eliminates distributed clock drift (S-1)
- **Lock**: `LockReleaseError` no longer masks original exceptions in context manager (S-2)
- **Connection**: `aclose()` now closes all async clients across all event loops (S-3)
- **PubSub**: `listen()` refactored with `get_message()` polling, `stop()` method, and `timeout` parameter for graceful shutdown (S-4)
- **Stream**: `StreamMessage._consumer` typed as `StreamConsumer | AsyncStreamConsumer | None` instead of `Any` (S-5)
- **Cache**: `delete()` now calls `after` hook on success (final review fix)
- **Connection**: `aclose()` logs debug message on client close failure instead of silent pass (final review fix)

### Stats
- 414 tests (up from 336), 0 failures
- 36 files changed, +2199 -312 lines

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
