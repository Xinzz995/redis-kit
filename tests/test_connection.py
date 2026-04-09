import fakeredis
import pytest

from redis_kit.config import ConnectionConfig
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
