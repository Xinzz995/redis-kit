import asyncio
from unittest.mock import AsyncMock, MagicMock

import fakeredis
import pytest

from redis_kit.config import ClusterConfig, ConnectionConfig, SentinelConfig
from redis_kit.connection import ConnectionManager


class TestConnectionManagerInit:
    def test_create_with_url(self):
        conn = ConnectionManager(url="redis://localhost:6379/0")
        assert conn._url == "redis://localhost:6379/0"
        conn.close()

    def test_create_with_config(self):
        config = ConnectionConfig(host="myhost", port=6380, db=2)
        conn = ConnectionManager(config=config)
        assert conn._config.host == "myhost"
        conn.close()

    def test_create_with_no_args_uses_defaults(self):
        conn = ConnectionManager()
        assert conn._config.host == "localhost"
        conn.close()

    def test_url_takes_precedence_over_config(self):
        config = ConnectionConfig(host="myhost")
        conn = ConnectionManager(url="redis://otherhost:6379/0", config=config)
        assert conn._url == "redis://otherhost:6379/0"
        conn.close()


class TestConnectionManagerSync:
    def test_sync_client_is_lazy(self):
        conn = ConnectionManager()
        assert conn._sync_client is None
        conn.close()

    def test_sync_client_returns_redis_instance(self):
        conn = ConnectionManager._from_clients(sync_client=fakeredis.FakeRedis())
        client = conn.sync_client
        assert client is not None
        client.set("test", "value")
        assert client.get("test") == b"value"
        conn.close()

    def test_close_cleans_up(self):
        conn = ConnectionManager._from_clients(sync_client=fakeredis.FakeRedis())
        _ = conn.sync_client
        conn.close()
        assert conn._sync_client is None


class TestConnectionManagerAsync:
    @pytest.mark.asyncio
    async def test_async_client_returns_redis_instance(self):
        conn = ConnectionManager._from_clients(async_client=fakeredis.aioredis.FakeRedis())
        client = conn.async_client
        await client.set("test", "value")
        result = await client.get("test")
        assert result == b"value"
        await conn.aclose()

    @pytest.mark.asyncio
    async def test_aclose_cleans_up(self):
        conn = ConnectionManager._from_clients(async_client=fakeredis.aioredis.FakeRedis())
        _ = conn.async_client
        await conn.aclose()


class TestAcloseAllAsyncClients:
    @pytest.mark.asyncio
    async def test_aclose_closes_all_registered_async_clients(self):
        """aclose() must drain every entry in _async_clients, not just the current loop's."""
        conn = ConnectionManager()

        # Fabricate two mock clients registered under two distinct fake loops.
        mock_loop_a = MagicMock(spec=asyncio.AbstractEventLoop)
        mock_loop_b = MagicMock(spec=asyncio.AbstractEventLoop)
        mock_client_a = AsyncMock()
        mock_client_b = AsyncMock()

        conn._async_clients[mock_loop_a] = mock_client_a
        conn._async_clients[mock_loop_b] = mock_client_b

        await conn.aclose()

        mock_client_a.aclose.assert_awaited_once()
        mock_client_b.aclose.assert_awaited_once()
        assert len(conn._async_clients) == 0

    @pytest.mark.asyncio
    async def test_aclose_clears_registry_even_when_client_raises(self):
        """Registry is cleared even if one client's aclose() raises."""
        conn = ConnectionManager()

        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        bad_client = AsyncMock()
        bad_client.aclose.side_effect = RuntimeError("connection gone")

        conn._async_clients[mock_loop] = bad_client

        # Should not raise.
        await conn.aclose()

        assert len(conn._async_clients) == 0

    @pytest.mark.asyncio
    async def test_aclose_is_idempotent(self):
        """Calling aclose() twice must not raise."""
        conn = ConnectionManager._from_clients(async_client=fakeredis.aioredis.FakeRedis())
        await conn.aclose()
        await conn.aclose()  # second call — registry already empty


class TestConnectionManagerCloseSafety:
    def test_close_thread_safe(self):
        """close() should acquire _sync_lock and set sync_client to None."""
        from unittest.mock import MagicMock

        mgr = ConnectionManager._from_clients(sync_client=MagicMock())
        assert mgr._sync_client is not None
        mgr.close()
        assert mgr._sync_client is None


class TestConnectionManagerTopology:
    def test_standalone_topology(self):
        conn = ConnectionManager()
        assert conn.topology == "standalone"
        assert conn.is_cluster is False
        assert conn.is_sentinel is False
        conn.close()

    def test_sentinel_topology(self):
        config = SentinelConfig(sentinels=[("localhost", 26379)], service_name="mymaster")
        conn = ConnectionManager(config=config)
        assert conn.topology == "sentinel"
        assert conn.is_sentinel is True
        assert conn.is_cluster is False
        conn.close()

    def test_cluster_topology(self):
        config = ClusterConfig(startup_nodes=[("localhost", 6379)])
        conn = ConnectionManager(config=config)
        assert conn.topology == "cluster"
        assert conn.is_cluster is True
        assert conn.is_sentinel is False
        conn.close()
