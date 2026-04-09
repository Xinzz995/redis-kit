# Sentinel & Cluster Topology Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Redis Sentinel and Cluster topology support to redis-py-kit via config polymorphism, so users switch topology by changing the Config object with zero downstream module changes.

**Architecture:** New `SentinelConfig` / `ClusterConfig` frozen dataclasses drive `ConnectionManager`'s build logic via `isinstance` dispatch. Cache `get_many`/`set_many` auto-degrade in Cluster mode using slot grouping. Lock keys use `{hash_tag}` in Cluster mode to keep Lua scripts on one slot.

**Tech Stack:** Python 3.11+, redis-py >= 7.4.0 (includes `redis.sentinel`, `redis.cluster`, `redis.asyncio.sentinel`, `redis.asyncio.cluster`), fakeredis[lua] for testing

---

## File Structure

```
redis_kit/
├── config.py                    # MODIFY: add SentinelConfig, ClusterConfig
├── connection.py                # MODIFY: add Sentinel/Cluster build methods, is_cluster, topology
├── exceptions.py                # MODIFY: add TopologyConstraintError
├── cache/
│   ├── _cluster.py              # CREATE: group_keys_by_slot() utility
│   ├── cache.py                 # MODIFY: add is_cluster param, Cluster get_many/set_many
│   └── async_cache.py           # MODIFY: same as cache.py for async
├── lock/
│   ├── lock.py                  # MODIFY: add is_cluster param, hash tag key
│   └── async_lock.py            # MODIFY: same as lock.py for async
└── __init__.py                  # MODIFY: export new types

tests/
├── test_config.py               # MODIFY: add SentinelConfig/ClusterConfig tests
├── test_connection.py           # MODIFY: add topology dispatch tests
├── test_exceptions.py           # MODIFY: add TopologyConstraintError test
├── test_cache_cluster.py        # CREATE: Cluster cache adaptation tests
└── test_lock_cluster.py         # CREATE: Cluster lock hash tag tests
```

---

## Task 1: Config — SentinelConfig & ClusterConfig

**Files:**
- Modify: `redis_kit/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for SentinelConfig**

Append to `tests/test_config.py`:

```python
from redis_kit.config import SentinelConfig, ClusterConfig


class TestSentinelConfig:
    def test_required_fields(self):
        config = SentinelConfig(
            sentinels=[("sentinel1", 26379), ("sentinel2", 26379)],
            service_name="mymaster",
        )
        assert config.sentinels == [("sentinel1", 26379), ("sentinel2", 26379)]
        assert config.service_name == "mymaster"

    def test_defaults(self):
        config = SentinelConfig(sentinels=[("h", 26379)], service_name="m")
        assert config.db == 0
        assert config.password is None
        assert config.sentinel_password is None
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0
        assert config.socket_connect_timeout == 5.0
        assert config.decode_responses is False
        assert config.ssl is False

    def test_frozen(self):
        import pytest
        config = SentinelConfig(sentinels=[("h", 26379)], service_name="m")
        with pytest.raises(AttributeError):
            config.service_name = "other"  # type: ignore[misc]

    def test_custom_values(self):
        config = SentinelConfig(
            sentinels=[("s1", 26379), ("s2", 26380), ("s3", 26381)],
            service_name="mymaster",
            db=3,
            password="redis_pass",
            sentinel_password="sentinel_pass",
            max_connections=50,
            ssl=True,
        )
        assert len(config.sentinels) == 3
        assert config.password == "redis_pass"
        assert config.sentinel_password == "sentinel_pass"
        assert config.max_connections == 50
        assert config.ssl is True


class TestClusterConfig:
    def test_required_fields(self):
        config = ClusterConfig(
            startup_nodes=[("node1", 6379), ("node2", 6380)],
        )
        assert config.startup_nodes == [("node1", 6379), ("node2", 6380)]

    def test_defaults(self):
        config = ClusterConfig(startup_nodes=[("h", 6379)])
        assert config.password is None
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0
        assert config.socket_connect_timeout == 5.0
        assert config.decode_responses is False
        assert config.ssl is False
        assert config.read_from_replicas is False

    def test_frozen(self):
        import pytest
        config = ClusterConfig(startup_nodes=[("h", 6379)])
        with pytest.raises(AttributeError):
            config.password = "x"  # type: ignore[misc]

    def test_custom_values(self):
        config = ClusterConfig(
            startup_nodes=[("n1", 6379), ("n2", 6380), ("n3", 6381)],
            password="secret",
            max_connections=50,
            read_from_replicas=True,
            ssl=True,
        )
        assert len(config.startup_nodes) == 3
        assert config.password == "secret"
        assert config.read_from_replicas is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_config.py -v -k "Sentinel or Cluster"`
Expected: FAIL — `ImportError: cannot import name 'SentinelConfig'`

- [ ] **Step 3: Implement SentinelConfig and ClusterConfig**

Add to `redis_kit/config.py` after `NamespaceConfig`:

```python
@dataclass(frozen=True)
class SentinelConfig:
    """Redis Sentinel configuration."""

    sentinels: list[tuple[str, int]]
    service_name: str
    db: int = 0
    password: str | None = None
    sentinel_password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False


@dataclass(frozen=True)
class ClusterConfig:
    """Redis Cluster configuration."""

    startup_nodes: list[tuple[str, int]]
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False
    read_from_replicas: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_config.py -v`
Expected: All tests PASS (10 existing + 8 new = 18)

- [ ] **Step 5: Lint and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run ruff check redis_kit/config.py tests/test_config.py`

```bash
git add redis_kit/config.py tests/test_config.py
git commit -m "feat: add SentinelConfig and ClusterConfig frozen dataclasses"
```

---

## Task 2: Exceptions — TopologyConstraintError

**Files:**
- Modify: `redis_kit/exceptions.py`
- Modify: `tests/test_exceptions.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_exceptions.py` in `TestExceptionHierarchy`:

```python
    def test_topology_constraint_error(self):
        from redis_kit.exceptions import TopologyConstraintError
        with pytest.raises(RedisKitError):
            raise TopologyConstraintError("cross-slot operation not supported")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_exceptions.py::TestExceptionHierarchy::test_topology_constraint_error -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement TopologyConstraintError**

Add to `redis_kit/exceptions.py` before `# --- Fallback Policy ---`:

```python
# --- Topology ---


class TopologyConstraintError(RedisKitError):
    """Operation not supported under current topology (e.g., cross-slot in Cluster)."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_exceptions.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add redis_kit/exceptions.py tests/test_exceptions.py
git commit -m "feat: add TopologyConstraintError exception"
```

---

## Task 3: ConnectionManager — Sentinel & Cluster Build Methods

**Files:**
- Modify: `redis_kit/connection.py`
- Modify: `tests/test_connection.py`

- [ ] **Step 1: Write failing tests for topology properties and Sentinel/Cluster dispatch**

Append to `tests/test_connection.py`:

```python
from redis_kit.config import SentinelConfig, ClusterConfig


class TestConnectionManagerTopology:
    def test_standalone_topology(self):
        conn = ConnectionManager()
        assert conn.topology == "standalone"
        assert conn.is_cluster is False
        assert conn.is_sentinel is False
        conn.close()

    def test_sentinel_topology(self):
        config = SentinelConfig(
            sentinels=[("localhost", 26379)],
            service_name="mymaster",
        )
        conn = ConnectionManager(config=config)
        assert conn.topology == "sentinel"
        assert conn.is_sentinel is True
        assert conn.is_cluster is False
        conn.close()

    def test_cluster_topology(self):
        config = ClusterConfig(
            startup_nodes=[("localhost", 6379)],
        )
        conn = ConnectionManager(config=config)
        assert conn.topology == "cluster"
        assert conn.is_cluster is True
        assert conn.is_sentinel is False
        conn.close()

    def test_url_with_config_type_preserved(self):
        config = SentinelConfig(
            sentinels=[("localhost", 26379)],
            service_name="mymaster",
        )
        conn = ConnectionManager(config=config)
        assert conn.is_sentinel is True
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_connection.py::TestConnectionManagerTopology -v`
Expected: FAIL — `AttributeError: 'ConnectionManager' object has no attribute 'topology'`

- [ ] **Step 3: Implement topology properties and build dispatch**

Modify `redis_kit/connection.py`. Update the type annotation for config parameter and add topology properties and Sentinel/Cluster build methods:

Update imports at top of file:
```python
from redis_kit.config import ClusterConfig, ConnectionConfig, SentinelConfig
```

Update `__init__` signature:
```python
    def __init__(
        self,
        url: str | None = None,
        config: ConnectionConfig | SentinelConfig | ClusterConfig | None = None,
    ) -> None:
        self._url = url
        self._config = config or ConnectionConfig()
        self._sync_client: redis.Redis | None = None
        self._sync_lock = threading.Lock()
        self._async_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, redis.asyncio.Redis] = (
            weakref.WeakKeyDictionary()
        )
        self._async_lock = threading.Lock()
```

Add topology properties after `_from_clients`:
```python
    @property
    def is_cluster(self) -> bool:
        """Whether this is a Cluster topology."""
        return isinstance(self._config, ClusterConfig)

    @property
    def is_sentinel(self) -> bool:
        """Whether this is a Sentinel topology."""
        return isinstance(self._config, SentinelConfig)

    @property
    def topology(self) -> str:
        """Current topology type string."""
        if isinstance(self._config, ClusterConfig):
            return "cluster"
        if isinstance(self._config, SentinelConfig):
            return "sentinel"
        return "standalone"
```

Replace `_build_sync_client` with dispatch:
```python
    def _build_sync_client(self) -> redis.Redis:
        if isinstance(self._config, SentinelConfig):
            return self._build_sentinel_sync()
        if isinstance(self._config, ClusterConfig):
            return self._build_cluster_sync()
        return self._build_standalone_sync()

    def _build_standalone_sync(self) -> redis.Redis:
        if self._url:
            return redis.Redis.from_url(
                self._url,
                max_connections=self._config.max_connections,
                socket_timeout=self._config.socket_timeout,
                socket_connect_timeout=self._config.socket_connect_timeout,
                decode_responses=self._config.decode_responses,
            )
        return redis.Redis(
            host=self._config.host,
            port=self._config.port,
            db=self._config.db,
            password=self._config.password,
            max_connections=self._config.max_connections,
            socket_timeout=self._config.socket_timeout,
            socket_connect_timeout=self._config.socket_connect_timeout,
            decode_responses=self._config.decode_responses,
            ssl=self._config.ssl,
        )

    def _build_sentinel_sync(self) -> redis.Redis:
        cfg = self._config  # type: SentinelConfig
        sentinel = redis.sentinel.Sentinel(
            cfg.sentinels,
            password=cfg.sentinel_password,
            socket_timeout=cfg.socket_timeout,
        )
        return sentinel.master_for(
            cfg.service_name,
            password=cfg.password,
            db=cfg.db,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
        )

    def _build_cluster_sync(self) -> redis.Redis:
        from redis.cluster import ClusterNode, RedisCluster
        cfg = self._config  # type: ClusterConfig
        nodes = [ClusterNode(h, p) for h, p in cfg.startup_nodes]
        return RedisCluster(
            startup_nodes=nodes,
            password=cfg.password,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
            ssl=cfg.ssl,
        )
```

Replace `_build_async_client` with the same dispatch pattern:
```python
    def _build_async_client(self) -> redis.asyncio.Redis:
        if isinstance(self._config, SentinelConfig):
            return self._build_sentinel_async()
        if isinstance(self._config, ClusterConfig):
            return self._build_cluster_async()
        return self._build_standalone_async()

    def _build_standalone_async(self) -> redis.asyncio.Redis:
        if self._url:
            return redis.asyncio.Redis.from_url(
                self._url,
                max_connections=self._config.max_connections,
                socket_timeout=self._config.socket_timeout,
                socket_connect_timeout=self._config.socket_connect_timeout,
                decode_responses=self._config.decode_responses,
            )
        return redis.asyncio.Redis(
            host=self._config.host,
            port=self._config.port,
            db=self._config.db,
            password=self._config.password,
            max_connections=self._config.max_connections,
            socket_timeout=self._config.socket_timeout,
            socket_connect_timeout=self._config.socket_connect_timeout,
            decode_responses=self._config.decode_responses,
            ssl=self._config.ssl,
        )

    def _build_sentinel_async(self) -> redis.asyncio.Redis:
        cfg = self._config  # type: SentinelConfig
        sentinel = redis.asyncio.sentinel.Sentinel(
            cfg.sentinels,
            password=cfg.sentinel_password,
            socket_timeout=cfg.socket_timeout,
        )
        return sentinel.master_for(
            cfg.service_name,
            password=cfg.password,
            db=cfg.db,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
        )

    def _build_cluster_async(self) -> redis.asyncio.Redis:
        from redis.asyncio.cluster import ClusterNode, RedisCluster
        cfg = self._config  # type: ClusterConfig
        nodes = [ClusterNode(h, p) for h, p in cfg.startup_nodes]
        return RedisCluster(
            startup_nodes=nodes,
            password=cfg.password,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
            ssl=cfg.ssl,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_connection.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest -v`
Expected: All 148+ tests PASS

- [ ] **Step 6: Commit**

```bash
git add redis_kit/connection.py tests/test_connection.py
git commit -m "feat: add Sentinel/Cluster topology support to ConnectionManager"
```

---

## Task 4: Cache Cluster Adaptation — group_keys_by_slot + is_cluster

**Files:**
- Create: `redis_kit/cache/_cluster.py`
- Modify: `redis_kit/cache/cache.py`
- Modify: `redis_kit/cache/async_cache.py`
- Create: `tests/test_cache_cluster.py`

- [ ] **Step 1: Create _cluster.py utility**

Create `redis_kit/cache/_cluster.py`:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Any


def group_keys_by_slot(client: Any, keys: list[str]) -> dict[int, list[str]]:
    """Group Redis keys by CRC16 slot for Cluster multi-key operations."""
    groups: dict[int, list[str]] = defaultdict(list)
    for key in keys:
        slot = client.keyslot(key)
        groups[slot].append(key)
    return groups
```

- [ ] **Step 2: Write failing tests for Cluster cache adaptation**

Create `tests/test_cache_cluster.py`:

```python
import fakeredis

from redis_kit.cache.cache import Cache


class TestCacheClusterMode:
    """Test Cache behavior with is_cluster=True using fakeredis (simulated)."""

    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_is_cluster_flag_stored(self):
        cache = Cache(self.client, prefix="test", is_cluster=True, ttl_jitter=0)
        assert cache._is_cluster is True

    def test_is_cluster_default_false(self):
        cache = Cache(self.client, prefix="test", ttl_jitter=0)
        assert cache._is_cluster is False

    def test_get_many_works_in_cluster_mode(self):
        """In cluster mode, get_many falls back to individual GETs."""
        cache = Cache(self.client, prefix="test", is_cluster=True, ttl_jitter=0)
        cache.set("a", 1)
        cache.set("b", 2)
        result = cache.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2, "c": None}

    def test_set_many_works_in_cluster_mode(self):
        """In cluster mode, set_many falls back to individual SETs."""
        cache = Cache(self.client, prefix="test", is_cluster=True, ttl_jitter=0)
        cache.set_many({"a": 1, "b": 2}, ttl=3600)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_standalone_get_many_unchanged(self):
        """Standalone mode still uses MGET pipeline."""
        cache = Cache(self.client, prefix="test", is_cluster=False, ttl_jitter=0)
        cache.set("a", 1)
        cache.set("b", 2)
        result = cache.get_many(["a", "b"])
        assert result == {"a": 1, "b": 2}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_cache_cluster.py -v`
Expected: FAIL — `TypeError: Cache.__init__() got an unexpected keyword argument 'is_cluster'`

- [ ] **Step 4: Add is_cluster to Cache constructor and adapt get_many/set_many**

Modify `redis_kit/cache/cache.py`:

Update `Cache.__init__` to add `is_cluster` parameter:
```python
    def __init__(
        self,
        client: redis.Redis,
        prefix: str = "",
        serializer: Serializer | None = None,
        compressor: Compressor | None = None,
        ttl_jitter: float = 0.1,
        fallback_policy: FallbackPolicy | None = None,
        hooks: list[CommandHook] | None = None,
        is_cluster: bool = False,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._pipeline = DataPipeline(serializer, compressor)
        self._ttl_jitter = ttl_jitter
        self._fallback = fallback_policy or FallbackPolicy()
        self._hooks = hooks or []
        self._is_cluster = is_cluster
```

Replace `get_many`:
```python
    def get_many(self, keys: list[str]) -> dict[str, Any]:
        full_keys = [self._make_key(k) for k in keys]
        if self._is_cluster:
            raw_values = self._cluster_mget(full_keys)
        else:
            raw_values = self._client.mget(full_keys)
        result = {}
        for key, raw in zip(keys, raw_values):
            val = self._pipeline.decode(raw)
            result[key] = val if val is not _MISS else None
        return result

    def _cluster_mget(self, keys: list[str]) -> list[bytes | None]:
        """Cluster-safe MGET: individual GET per key."""
        return [self._client.get(k) for k in keys]
```

Replace `set_many`:
```python
    def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        resolved_ttl = self._resolve_ttl(ttl)
        if self._is_cluster:
            for key, value in mapping.items():
                full_key = self._make_key(key)
                encoded = self._pipeline.encode(value)
                if resolved_ttl is not None and resolved_ttl > 0:
                    self._client.setex(full_key, resolved_ttl, encoded)
                else:
                    self._client.set(full_key, encoded)
        else:
            pipe = self._client.pipeline(transaction=False)
            for key, value in mapping.items():
                full_key = self._make_key(key)
                encoded = self._pipeline.encode(value)
                if resolved_ttl is not None and resolved_ttl > 0:
                    pipe.setex(full_key, resolved_ttl, encoded)
                else:
                    pipe.set(full_key, encoded)
            pipe.execute()
```

- [ ] **Step 5: Apply same changes to AsyncCache**

Modify `redis_kit/cache/async_cache.py`:

Update `AsyncCache.__init__` to add `is_cluster: bool = False` parameter and `self._is_cluster = is_cluster`.

Replace `get_many`:
```python
    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        full_keys = [self._make_key(k) for k in keys]
        if self._is_cluster:
            raw_values = [await self._client.get(k) for k in full_keys]
        else:
            raw_values = await self._client.mget(full_keys)
        result = {}
        for key, raw in zip(keys, raw_values):
            val = self._pipeline.decode(raw)
            result[key] = val if val is not _MISS else None
        return result
```

Replace `set_many`:
```python
    async def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        resolved_ttl = self._resolve_ttl(ttl)
        if self._is_cluster:
            for key, value in mapping.items():
                full_key = self._make_key(key)
                encoded = self._pipeline.encode(value)
                if resolved_ttl is not None and resolved_ttl > 0:
                    await self._client.setex(full_key, resolved_ttl, encoded)
                else:
                    await self._client.set(full_key, encoded)
        else:
            pipe = self._client.pipeline(transaction=False)
            for key, value in mapping.items():
                full_key = self._make_key(key)
                encoded = self._pipeline.encode(value)
                if resolved_ttl is not None and resolved_ttl > 0:
                    pipe.setex(full_key, resolved_ttl, encoded)
                else:
                    pipe.set(full_key, encoded)
            await pipe.execute()
```

- [ ] **Step 6: Run tests**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_cache_cluster.py tests/test_cache.py -v`
Expected: All tests PASS (existing cache tests + new cluster tests)

- [ ] **Step 7: Commit**

```bash
git add redis_kit/cache/_cluster.py redis_kit/cache/cache.py redis_kit/cache/async_cache.py tests/test_cache_cluster.py
git commit -m "feat: add Cluster adaptation for Cache get_many/set_many"
```

---

## Task 5: Lock Cluster Adaptation — Hash Tag Keys

**Files:**
- Modify: `redis_kit/lock/lock.py`
- Modify: `redis_kit/lock/async_lock.py`
- Create: `tests/test_lock_cluster.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_lock_cluster.py`:

```python
import fakeredis

from redis_kit.lock.lock import Lock


class TestLockClusterMode:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_is_cluster_flag(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        assert lock._is_cluster is True

    def test_cluster_key_has_hash_tag(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        key = lock._make_key("resource-1")
        assert key == "{test:lock:resource-1}"

    def test_standalone_key_no_hash_tag(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=False)
        key = lock._make_key("resource-1")
        assert key == "test:lock:resource-1"

    def test_cluster_lock_acquire_release(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        with lock("resource-1", timeout=10):
            assert self.client.exists(b"{test:lock:resource-1}")
        assert not self.client.exists(b"{test:lock:resource-1}")

    def test_cluster_reentrant_lock(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        with lock("resource-1", timeout=10, reentrant=True):
            with lock("resource-1", timeout=10, reentrant=True):
                assert True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_lock_cluster.py -v`
Expected: FAIL — `TypeError: Lock.__init__() got an unexpected keyword argument 'is_cluster'`

- [ ] **Step 3: Add is_cluster to Lock**

Modify `redis_kit/lock/lock.py`:

Update `Lock.__init__`:
```python
    def __init__(self, client: redis.Redis, prefix: str = "", is_cluster: bool = False) -> None:
        self._client = client
        self._prefix = prefix
        self._is_cluster = is_cluster
        self._release_script = self._client.register_script(RELEASE_LOCK)
        self._reentrant_acquire_script = self._client.register_script(REENTRANT_ACQUIRE)
        self._reentrant_release_script = self._client.register_script(REENTRANT_RELEASE)
        self._extend_script = self._client.register_script(EXTEND_LOCK)
        self._extend_reentrant_script = self._client.register_script(EXTEND_REENTRANT_LOCK)
        self._read_acquire_script = self._client.register_script(READ_ACQUIRE)
        self._read_release_script = self._client.register_script(READ_RELEASE)
        self._write_acquire_script = self._client.register_script(WRITE_ACQUIRE)
```

Update `_make_key`:
```python
    def _make_key(self, name: str) -> str:
        base = f"{self._prefix}:{name}" if self._prefix else name
        if self._is_cluster:
            return f"{{{base}}}"
        return base
```

- [ ] **Step 4: Add is_cluster to AsyncLock**

Modify `redis_kit/lock/async_lock.py`:

Update `AsyncLock.__init__`:
```python
    def __init__(self, client: redis.asyncio.Redis, prefix: str = "", is_cluster: bool = False) -> None:
        self._client = client
        self._prefix = prefix
        self._is_cluster = is_cluster
        self._release_script = self._client.register_script(RELEASE_LOCK)
        self._reentrant_acquire_script = self._client.register_script(REENTRANT_ACQUIRE)
        self._reentrant_release_script = self._client.register_script(REENTRANT_RELEASE)
        self._extend_script = self._client.register_script(EXTEND_LOCK)
        self._extend_reentrant_script = self._client.register_script(EXTEND_REENTRANT_LOCK)
        self._read_acquire_script = self._client.register_script(READ_ACQUIRE)
        self._read_release_script = self._client.register_script(READ_RELEASE)
        self._write_acquire_script = self._client.register_script(WRITE_ACQUIRE)
```

Update `_make_key`:
```python
    def _make_key(self, name: str) -> str:
        base = f"{self._prefix}:{name}" if self._prefix else name
        if self._is_cluster:
            return f"{{{base}}}"
        return base
```

- [ ] **Step 5: Run tests**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_lock_cluster.py tests/test_lock.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add redis_kit/lock/lock.py redis_kit/lock/async_lock.py tests/test_lock_cluster.py
git commit -m "feat: add Cluster hash tag key support to Lock/AsyncLock"
```

---

## Task 6: Public API Exports & Final Integration

**Files:**
- Modify: `redis_kit/__init__.py`

- [ ] **Step 1: Update exports**

Modify `redis_kit/__init__.py`:

Add imports:
```python
from redis_kit.config import ClusterConfig, ConnectionConfig, NamespaceConfig, SentinelConfig
from redis_kit.exceptions import FallbackPolicy, RedisKitError, TopologyConstraintError
```

Add to `__all__`:
```python
    # Connection
    "ConnectionManager",
    "ConnectionConfig",
    "SentinelConfig",
    "ClusterConfig",
    "NamespaceConfig",
    ...
    # Exceptions
    "RedisKitError",
    "FallbackPolicy",
    "TopologyConstraintError",
```

- [ ] **Step 2: Verify imports**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run python -c "from redis_kit import ConnectionManager, SentinelConfig, ClusterConfig, TopologyConstraintError; print('All new imports OK')"`
Expected: "All new imports OK"

- [ ] **Step 3: Run full test suite**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Run linter**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run ruff check . && uv run ruff format --check .`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add redis_kit/__init__.py
git commit -m "feat: export SentinelConfig, ClusterConfig, TopologyConstraintError"
```

---

## Summary

| Task | Component | Steps |
|------|-----------|-------|
| 1 | Config (SentinelConfig, ClusterConfig) | 5 |
| 2 | Exceptions (TopologyConstraintError) | 5 |
| 3 | ConnectionManager (Sentinel/Cluster build + topology props) | 6 |
| 4 | Cache Cluster adaptation (is_cluster, get_many/set_many fallback) | 7 |
| 5 | Lock Cluster adaptation (hash tag keys) | 6 |
| 6 | Public API exports | 5 |
| **Total** | | **34 steps** |
