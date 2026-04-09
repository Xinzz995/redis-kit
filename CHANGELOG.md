# Changelog

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
