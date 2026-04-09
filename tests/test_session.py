import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.exceptions import SessionNotFoundError
from redis_kit.session.async_session import AsyncSessionManager
from redis_kit.session.session import SessionManager


class TestSessionManager:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make_manager(self, **kwargs):
        return SessionManager(self.client, prefix="session", ttl=1800, **kwargs)

    def test_create_returns_session_id(self):
        mgr = self._make_manager()
        sid = mgr.create({"user_id": 1, "role": "admin"})
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_get_returns_data(self):
        mgr = self._make_manager()
        sid = mgr.create({"user_id": 1, "role": "admin"})
        data = mgr.get(sid)
        assert data is not None
        assert data["user_id"] == "1"
        assert data["role"] == "admin"

    def test_get_nonexistent_returns_none(self):
        mgr = self._make_manager()
        assert mgr.get("nonexistent") is None

    def test_update_partial(self):
        mgr = self._make_manager()
        sid = mgr.create({"user_id": 1, "role": "admin"})
        mgr.update(sid, {"role": "superadmin"})
        data = mgr.get(sid)
        assert data["role"] == "superadmin"
        assert data["user_id"] == "1"

    def test_delete(self):
        mgr = self._make_manager()
        sid = mgr.create({"user_id": 1})
        mgr.delete(sid)
        assert mgr.get(sid) is None

    def test_refresh_extends_ttl(self):
        mgr = self._make_manager()
        sid = mgr.create({"user_id": 1})
        key = f"session:{sid}"
        original_ttl = self.client.ttl(key)
        assert original_ttl > 0
        mgr.refresh(sid)
        refreshed_ttl = self.client.ttl(key)
        assert refreshed_ttl > 0

    def test_exists(self):
        mgr = self._make_manager()
        sid = mgr.create({"user_id": 1})
        assert mgr.exists(sid) is True
        mgr.delete(sid)
        assert mgr.exists(sid) is False

    def test_update_nonexistent_raises(self):
        mgr = self._make_manager()
        from redis_kit.exceptions import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            mgr.update("nonexistent", {"key": "val"})

    def test_refresh_nonexistent_raises(self):
        mgr = self._make_manager()
        from redis_kit.exceptions import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            mgr.refresh("nonexistent")


class TestAsyncSessionManager:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    def _make_manager(self):
        return AsyncSessionManager(self.client, prefix="session", ttl=1800)

    @pytest.mark.asyncio
    async def test_create_and_get(self):
        mgr = self._make_manager()
        sid = await mgr.create({"user_id": 1, "role": "admin"})
        data = await mgr.get(sid)
        assert data["user_id"] == "1"
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        mgr = self._make_manager()
        assert await mgr.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_update(self):
        mgr = self._make_manager()
        sid = await mgr.create({"user_id": 1})
        await mgr.update(sid, {"role": "admin"})
        data = await mgr.get(sid)
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_delete(self):
        mgr = self._make_manager()
        sid = await mgr.create({"user_id": 1})
        await mgr.delete(sid)
        assert await mgr.get(sid) is None

    @pytest.mark.asyncio
    async def test_exists(self):
        mgr = self._make_manager()
        sid = await mgr.create({"user_id": 1})
        assert await mgr.exists(sid) is True
        await mgr.delete(sid)
        assert await mgr.exists(sid) is False

    @pytest.mark.asyncio
    async def test_refresh(self):
        mgr = self._make_manager()
        sid = await mgr.create({"user_id": 1})
        await mgr.refresh(sid)

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self):
        mgr = self._make_manager()
        with pytest.raises(SessionNotFoundError):
            await mgr.update("nonexistent", {"key": "val"})
