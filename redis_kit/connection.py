from __future__ import annotations

import asyncio
import threading
import weakref
from typing import Any

import redis
import redis.asyncio

from redis_kit.config import ConnectionConfig


class ConnectionManager:
    """Manages Redis connections with sync/async views.

    Connections are lazily initialized on first access.
    Async clients are isolated per event loop to prevent cross-loop reuse.
    """

    def __init__(
        self,
        url: str | None = None,
        config: ConnectionConfig | None = None,
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

    def _build_sync_client(self) -> redis.Redis:
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

    def _build_async_client(self) -> redis.asyncio.Redis:
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

    def close(self) -> None:
        """Close sync client and its connection pool."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        """Close async client for the current event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        client = self._async_clients.pop(loop, None)
        if client is not None:
            await client.aclose()
