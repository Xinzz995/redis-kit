from __future__ import annotations

import asyncio
import logging
import threading
import weakref
from typing import Any

import redis
import redis.asyncio

from redis_kit.config import ClusterConfig, ConnectionConfig, SentinelConfig

_logger = logging.getLogger("redis_kit")


class ConnectionManager:
    """Manages Redis connections with sync/async views.

    Connections are lazily initialized on first access.
    Async clients are isolated per event loop to prevent cross-loop reuse.
    """

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

    @classmethod
    def _from_clients(
        cls,
        sync_client: Any | None = None,
        async_client: Any | None = None,
    ) -> ConnectionManager:
        """Create a ConnectionManager with pre-built clients (for testing)."""
        instance = cls.__new__(cls)
        instance._url = None
        instance._config = ConnectionConfig()
        instance._sync_client = sync_client
        instance._sync_lock = threading.Lock()
        instance._async_clients = weakref.WeakKeyDictionary()
        instance._async_lock = threading.Lock()
        if async_client is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            instance._async_clients[loop] = async_client
        return instance

    @property
    def is_cluster(self) -> bool:
        return isinstance(self._config, ClusterConfig)

    @property
    def is_sentinel(self) -> bool:
        return isinstance(self._config, SentinelConfig)

    @property
    def topology(self) -> str:
        if isinstance(self._config, ClusterConfig):
            return "cluster"
        if isinstance(self._config, SentinelConfig):
            return "sentinel"
        return "standalone"

    @property
    def sync_client(self) -> redis.Redis:
        """Get or create the sync Redis client (thread-safe, lazy)."""
        if self._sync_client is None:
            with self._sync_lock:
                if self._sync_client is None:
                    self._sync_client = self._build_sync_client()
        return self._sync_client

    @property
    def async_client(self) -> redis.asyncio.Redis:
        """Get or create the async Redis client for the current event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as e:
            raise RuntimeError("async_client requires a running event loop") from e

        client = self._async_clients.get(loop)
        if client is None:
            with self._async_lock:
                client = self._async_clients.get(loop)
                if client is None:
                    client = self._build_async_client()
                    self._async_clients[loop] = client
        return client

    def _build_sync_client(self) -> Any:
        if isinstance(self._config, SentinelConfig):
            return self._build_sentinel_sync()
        if isinstance(self._config, ClusterConfig):
            return self._build_cluster_sync()
        return self._build_standalone_sync()

    def _build_standalone_sync(self) -> redis.Redis:
        if not isinstance(self._config, ConnectionConfig):
            raise TypeError(f"Expected ConnectionConfig, got {type(self._config)}")
        cfg = self._config
        if self._url:
            return redis.Redis.from_url(
                self._url,
                max_connections=cfg.max_connections,
                socket_timeout=cfg.socket_timeout,
                socket_connect_timeout=cfg.socket_connect_timeout,
                decode_responses=cfg.decode_responses,
                ssl=cfg.ssl,
            )
        return redis.Redis(
            host=cfg.host,
            port=cfg.port,
            db=cfg.db,
            password=cfg.password,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
            ssl=cfg.ssl,
        )

    def _build_sentinel_sync(self) -> redis.Redis:
        if not isinstance(self._config, SentinelConfig):
            raise TypeError(f"Expected SentinelConfig, got {type(self._config)}")
        cfg = self._config
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

    def _build_cluster_sync(self) -> Any:
        from redis.cluster import ClusterNode, RedisCluster

        if not isinstance(self._config, ClusterConfig):
            raise TypeError(f"Expected ClusterConfig, got {type(self._config)}")
        cfg = self._config
        nodes = [ClusterNode(h, p) for h, p in cfg.startup_nodes]
        return RedisCluster(
            startup_nodes=nodes,
            password=cfg.password,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
            ssl=cfg.ssl,
            read_from_replicas=cfg.read_from_replicas,
        )

    def _build_async_client(self) -> Any:
        if isinstance(self._config, SentinelConfig):
            return self._build_sentinel_async()
        if isinstance(self._config, ClusterConfig):
            return self._build_cluster_async()
        return self._build_standalone_async()

    def _build_standalone_async(self) -> redis.asyncio.Redis:
        if not isinstance(self._config, ConnectionConfig):
            raise TypeError(f"Expected ConnectionConfig, got {type(self._config)}")
        cfg = self._config
        if self._url:
            return redis.asyncio.Redis.from_url(
                self._url,
                max_connections=cfg.max_connections,
                socket_timeout=cfg.socket_timeout,
                socket_connect_timeout=cfg.socket_connect_timeout,
                decode_responses=cfg.decode_responses,
                ssl=cfg.ssl,
            )
        return redis.asyncio.Redis(
            host=cfg.host,
            port=cfg.port,
            db=cfg.db,
            password=cfg.password,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
            ssl=cfg.ssl,
        )

    def _build_sentinel_async(self) -> redis.asyncio.Redis:
        if not isinstance(self._config, SentinelConfig):
            raise TypeError(f"Expected SentinelConfig, got {type(self._config)}")
        cfg = self._config
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

    def _build_cluster_async(self) -> Any:
        from redis.asyncio.cluster import ClusterNode, RedisCluster

        if not isinstance(self._config, ClusterConfig):
            raise TypeError(f"Expected ClusterConfig, got {type(self._config)}")
        cfg = self._config
        nodes = [ClusterNode(h, p) for h, p in cfg.startup_nodes]
        return RedisCluster(
            startup_nodes=nodes,
            password=cfg.password,
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout,
            socket_connect_timeout=cfg.socket_connect_timeout,
            decode_responses=cfg.decode_responses,
            ssl=cfg.ssl,
            read_from_replicas=cfg.read_from_replicas,
        )

    def close(self) -> None:
        """Close sync client and its connection pool."""
        with self._sync_lock:
            if self._sync_client is not None:
                self._sync_client.close()
                self._sync_client = None

    async def aclose(self) -> None:
        """Close all async clients across all event loops.

        Snapshots and clears the entire _async_clients registry before
        awaiting each client's aclose(), so callers from any loop trigger
        a full cleanup rather than only closing their own loop's client.
        """
        with self._async_lock:
            clients = list(self._async_clients.values())
            self._async_clients.clear()
        for client in clients:
            try:
                await client.aclose()
            except Exception:
                _logger.debug("Error closing async Redis client during aclose()", exc_info=True)
