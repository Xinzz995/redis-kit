from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime
from typing import TypeVar

from redis_kit.exceptions import EntityNotFoundError, OptimisticLockError, RepositoryError
from redis_kit.repository._base_repo import RepositoryBase
from redis_kit.repository._hash import _NONE_SENTINEL, from_hash, to_hash
from redis_kit.repository.model import BaseModel

T = TypeVar("T", bound=BaseModel)


class AsyncRepository(RepositoryBase):
    """Async Redis-backed repository with CRUD, versioning, soft delete, and audit."""

    async def save(self, entity: T) -> T:
        now = datetime.now(tz=UTC)

        if not entity.id:
            # New entity
            entity = dataclasses.replace(
                entity,
                id=uuid.uuid4().hex,
                version=1,
                created_at=now,
                updated_at=now,
            )
        else:
            # Update existing — atomic optimistic lock check + write + history
            key = self._make_key(entity.id)
            history_key = self._history_key(entity.id)
            entity = dataclasses.replace(
                entity,
                version=entity.version + 1,
                updated_at=now,
            )
            hash_data = to_hash(entity)
            # Flatten: [expected_version, max_history, field1, val1, field2, val2, ...]
            flat_args: list[str] = [str(entity.version - 1), self._max_history_arg()]
            for field_name, value in hash_data.items():
                flat_args.append(field_name)
                flat_args.append(value)
            # Lua returns 0 on conflict, 1 on success (history written atomically)
            result = await self._lock_set_script(keys=[key, history_key], args=flat_args)
            if result == 0:
                raise OptimisticLockError(f"Version conflict for entity '{entity.id}': expected {entity.version - 1}")

            return entity

        key = self._make_key(entity.id)
        pipe = self._client.pipeline(transaction=True)
        pipe.hset(key, mapping=to_hash(entity))
        pipe.sadd(self._index_key, entity.id)
        await pipe.execute()
        return entity

    async def find(self, entity_id: str) -> T | None:
        key = self._make_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            return None
        entity = from_hash(data, self._model_class)
        if entity.deleted:
            return None
        return entity

    async def find_including_deleted(self, entity_id: str) -> T | None:
        key = self._make_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            return None
        return from_hash(data, self._model_class)

    async def delete(self, entity_id: str) -> None:
        key = self._make_key(entity_id)
        history_key = self._history_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            raise EntityNotFoundError(f"Entity '{entity_id}' not found")
        entity = from_hash(data, self._model_class)
        now = datetime.now(tz=UTC)
        new_version = entity.version + 1
        flat_args: list[str] = [
            str(entity.version),
            self._max_history_arg(),
            "deleted",
            "1",
            "deleted_at",
            now.isoformat(),
            "version",
            str(new_version),
            "updated_at",
            now.isoformat(),
        ]
        allowed = await self._lock_partial_set_script(keys=[key, history_key], args=flat_args)
        if not allowed:
            raise OptimisticLockError(f"Version conflict for entity '{entity_id}': expected {entity.version}")

    async def hard_delete(self, entity_id: str) -> None:
        key = self._make_key(entity_id)
        pipe = self._client.pipeline(transaction=False)
        pipe.delete(key)
        pipe.delete(self._history_key(entity_id))
        pipe.srem(self._index_key, entity_id)
        await pipe.execute()

    async def restore(self, entity_id: str) -> T:
        key = self._make_key(entity_id)
        history_key = self._history_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            raise EntityNotFoundError(f"Entity '{entity_id}' not found")
        entity = from_hash(data, self._model_class)
        if not entity.deleted:
            raise RepositoryError(f"Entity '{entity_id}' is not deleted")
        now = datetime.now(tz=UTC)
        new_version = entity.version + 1
        flat_args: list[str] = [
            str(entity.version),
            self._max_history_arg(),
            "deleted",
            "0",
            "deleted_at",
            _NONE_SENTINEL,
            "version",
            str(new_version),
            "updated_at",
            now.isoformat(),
        ]
        allowed = await self._lock_partial_set_script(keys=[key, history_key], args=flat_args)
        if not allowed:
            raise OptimisticLockError(f"Version conflict for entity '{entity_id}': expected {entity.version}")
        return dataclasses.replace(entity, deleted=False, deleted_at=None, version=new_version, updated_at=now)

    async def find_all(self) -> list[T]:
        ids = await self._client.smembers(self._index_key)
        if not ids:
            return []
        decoded_ids = []
        for raw_id in ids:
            eid = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
            decoded_ids.append(eid)

        if self._is_cluster:
            all_data = [await self._client.hgetall(self._make_key(eid)) for eid in decoded_ids]
        else:
            pipe = self._client.pipeline(transaction=False)
            for eid in decoded_ids:
                pipe.hgetall(self._make_key(eid))
            all_data = await pipe.execute()
        result = []
        for data in all_data:
            if not data:
                continue
            entity = from_hash(data, self._model_class)
            if not entity.deleted:
                result.append(entity)
        return result

    async def get_history(self, entity_id: str) -> list[T]:
        history_data = await self._client.lrange(self._history_key(entity_id), 0, -1)
        result = []
        for item in history_data:
            raw = item.decode() if isinstance(item, bytes) else item
            hash_data = json.loads(raw)
            entity = from_hash(hash_data, self._model_class)
            result.append(entity)
        return result
