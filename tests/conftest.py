import fakeredis
import pytest


@pytest.fixture
def redis_client():
    """Provide a fresh fakeredis client for each test."""
    client = fakeredis.FakeRedis(decode_responses=False)
    yield client
    client.flushall()
    client.close()


@pytest.fixture
def async_redis_client():
    """Provide a fresh async fakeredis client for each test."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    yield client


@pytest.fixture(autouse=True)
async def cleanup_async_client(async_redis_client):
    yield
    await async_redis_client.flushall()
    await async_redis_client.aclose()
