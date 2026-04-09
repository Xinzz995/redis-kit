from dataclasses import dataclass

import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.exceptions import (
    EntityNotFoundError,
    OptimisticLockError,
    RedisKitError,
    RepositoryError,
)
from redis_kit.repository.async_repository import AsyncRepository
from redis_kit.repository.model import BaseModel
from redis_kit.repository.repository import Repository


@dataclass
class SampleEntity(BaseModel):
    name: str = ""
    value: str = ""


class TestBaseModel:
    def test_defaults(self):
        e = SampleEntity()
        assert e.id == ""
        assert e.version == 0
        assert e.created_at is None
        assert e.deleted is False

    def test_custom_fields(self):
        e = SampleEntity(name="foo", value="bar")
        assert e.name == "foo"
        assert e.value == "bar"

    def test_inherits_metadata(self):
        e = SampleEntity(id="123", version=3)
        assert e.id == "123"
        assert e.version == 3


class TestRepositoryExceptions:
    def test_hierarchy(self):
        with pytest.raises(RedisKitError):
            raise RepositoryError("fail")
        with pytest.raises(RepositoryError):
            raise EntityNotFoundError("not found")
        with pytest.raises(RepositoryError):
            raise OptimisticLockError("conflict")


class TestRepositoryCRUD:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make_repo(self):
        return Repository(self.client, SampleEntity, prefix="test")

    def test_save_new_entity(self):
        repo = self._make_repo()
        entity = SampleEntity(name="max_retries", value="3")
        saved = repo.save(entity)
        assert saved.id != ""
        assert saved.version == 1
        assert saved.created_at is not None
        assert saved.updated_at is not None

    def test_find_by_id(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="val"))
        found = repo.find(saved.id)
        assert found is not None
        assert found.name == "key"
        assert found.value == "val"
        assert found.version == 1

    def test_find_nonexistent(self):
        repo = self._make_repo()
        assert repo.find("nonexistent") is None

    def test_update_increments_version(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="v1"))
        saved.value = "v2"
        updated = repo.save(saved)
        assert updated.version == 2
        assert updated.value == "v2"
        assert updated.updated_at is not None

    def test_find_all(self):
        repo = self._make_repo()
        repo.save(SampleEntity(name="a", value="1"))
        repo.save(SampleEntity(name="b", value="2"))
        all_entities = repo.find_all()
        assert len(all_entities) == 2


class TestRepositoryOptimisticLock:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make_repo(self):
        return Repository(self.client, SampleEntity, prefix="test")

    def test_optimistic_lock_conflict(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="v1"))

        # Simulate concurrent read
        stale = repo.find(saved.id)

        # First update succeeds
        saved.value = "v2"
        repo.save(saved)

        # Stale update fails
        stale.value = "v3"
        with pytest.raises(OptimisticLockError):
            repo.save(stale)


class TestRepositorySoftDelete:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make_repo(self):
        return Repository(self.client, SampleEntity, prefix="test")

    def test_soft_delete(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="val"))
        repo.delete(saved.id)
        assert repo.find(saved.id) is None

    def test_find_including_deleted(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="val"))
        repo.delete(saved.id)
        found = repo.find_including_deleted(saved.id)
        assert found is not None
        assert found.deleted is True
        assert found.deleted_at is not None

    def test_restore(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="val"))
        repo.delete(saved.id)
        restored = repo.restore(saved.id)
        assert restored.deleted is False
        assert repo.find(saved.id) is not None

    def test_hard_delete(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="val"))
        repo.hard_delete(saved.id)
        assert repo.find(saved.id) is None
        assert repo.find_including_deleted(saved.id) is None

    def test_delete_nonexistent_raises(self):
        repo = self._make_repo()
        with pytest.raises(EntityNotFoundError):
            repo.delete("nonexistent")

    def test_find_all_excludes_deleted(self):
        repo = self._make_repo()
        s1 = repo.save(SampleEntity(name="a", value="1"))
        repo.save(SampleEntity(name="b", value="2"))
        repo.delete(s1.id)
        assert len(repo.find_all()) == 1


class TestRepositoryHistory:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make_repo(self):
        return Repository(self.client, SampleEntity, prefix="test")

    def test_history_on_update(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="v1"))
        saved.value = "v2"
        saved = repo.save(saved)
        saved.value = "v3"
        repo.save(saved)
        history = repo.get_history(saved.id)
        assert len(history) == 2  # v1 and v2
        assert history[0].value == "v2"  # Most recent first (LPUSH)
        assert history[1].value == "v1"

    def test_no_history_for_new(self):
        repo = self._make_repo()
        saved = repo.save(SampleEntity(name="key", value="v1"))
        assert len(repo.get_history(saved.id)) == 0


class TestAsyncRepository:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    def _make_repo(self):
        return AsyncRepository(self.client, SampleEntity, prefix="test")

    @pytest.mark.asyncio
    async def test_save_and_find(self):
        repo = self._make_repo()
        saved = await repo.save(SampleEntity(name="key", value="val"))
        found = await repo.find(saved.id)
        assert found is not None
        assert found.name == "key"
        assert found.version == 1

    @pytest.mark.asyncio
    async def test_soft_delete_and_restore(self):
        repo = self._make_repo()
        saved = await repo.save(SampleEntity(name="key", value="val"))
        await repo.delete(saved.id)
        assert await repo.find(saved.id) is None
        restored = await repo.restore(saved.id)
        assert restored.deleted is False

    @pytest.mark.asyncio
    async def test_optimistic_lock(self):
        repo = self._make_repo()
        saved = await repo.save(SampleEntity(name="k", value="v1"))
        stale = await repo.find(saved.id)
        saved.value = "v2"
        await repo.save(saved)
        stale.value = "v3"
        with pytest.raises(OptimisticLockError):
            await repo.save(stale)

    @pytest.mark.asyncio
    async def test_history(self):
        repo = self._make_repo()
        saved = await repo.save(SampleEntity(name="k", value="v1"))
        saved.value = "v2"
        saved = await repo.save(saved)
        history = await repo.get_history(saved.id)
        assert len(history) == 1
        assert history[0].value == "v1"
