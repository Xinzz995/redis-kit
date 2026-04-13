from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar

from redis_kit.exceptions import EntityNotFoundError, OptimisticLockError, RepositoryError
from redis_kit.repository._hash import from_hash, to_hash
from redis_kit.repository._lua import OPTIMISTIC_LOCK_PARTIAL_SET, OPTIMISTIC_LOCK_SET
from redis_kit.repository.model import BaseModel

if TYPE_CHECKING:
    import redis.asyncio

T = TypeVar("T", bound=BaseModel)


class AsyncRepository:
    """Async Redis-backed repository with CRUD, versioning, soft delete, and audit."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
        model_class: type[T],
        prefix: str = "",
        is_cluster: bool = False,
        max_history: int | None = None,
    ) -> None:
        self._client = client
        self._model_class = model_class
        self._prefix = prefix
        self._is_cluster = is_cluster
        self._max_history = max_history
        self._lock_set_script = self._client.register_script(OPTIMISTIC_LOCK_SET)
        self._lock_partial_set_script = self._client.register_script(OPTIMISTIC_LOCK_PARTIAL_SET)
        self._index_key = f"{self._prefix}:_index" if self._prefix else "_index"

    def _make_key(self, entity_id: str) -> str:
        return f"{self._prefix}:{entity_id}" if self._prefix else entity_id

    def _history_key(self, entity_id: str) -> str:
        return f"{self._make_key(entity_id)}:history"

    def _to_hash(self, entity: BaseModel) -> dict[str, str]:
        return to_hash(entity)

    def _from_hash(self, data: dict[bytes | str, bytes | str]) -> T:
        return from_hash(data, self._model_class)

    async def _append_history(self, entity: T) -> None:
        history_json = json.dumps(self._to_hash(entity))
        await self._client.lpush(self._history_key(entity.id), history_json)
        if self._max_history is not None:
            await self._client.ltrim(self._history_key(entity.id), 0, self._max_history - 1)

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
            # Update existing — atomic optimistic lock check + write
            key = self._make_key(entity.id)
            # Read current state for history (written only after lock succeeds)
            existing_data = await self._client.hgetall(key)

            entity = dataclasses.replace(
                entity,
                version=entity.version + 1,
                updated_at=now,
            )
            hash_data = self._to_hash(entity)
            # Flatten: [expected_version, field1, val1, field2, val2, ...]
            flat_args: list[str] = [str(entity.version - 1)]
            for field_name, value in hash_data.items():
                flat_args.append(field_name)
                flat_args.append(value)
            allowed = await self._lock_set_script(keys=[key], args=flat_args)
            if not allowed:
                raise OptimisticLockError(f"Version conflict for entity '{entity.id}': expected {entity.version - 1}")

            # Write history only after optimistic lock succeeds
            if existing_data:
                old_entity = self._from_hash(existing_data)
                await self._append_history(old_entity)

            await self._client.sadd(self._index_key, entity.id)
            return entity

        key = self._make_key(entity.id)
        pipe = self._client.pipeline(transaction=True)
        pipe.hset(key, mapping=self._to_hash(entity))
        pipe.sadd(self._index_key, entity.id)
        await pipe.execute()
        return entity

    async def find(self, entity_id: str) -> T | None:
        key = self._make_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            return None
        entity = self._from_hash(data)
        if entity.deleted:
            return None
        return entity

    async def find_including_deleted(self, entity_id: str) -> T | None:
        key = self._make_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            return None
        return self._from_hash(data)

    async def delete(self, entity_id: str) -> None:
        key = self._make_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            raise EntityNotFoundError(f"Entity '{entity_id}' not found")
        entity = self._from_hash(data)
        now = datetime.now(tz=UTC)
        new_version = entity.version + 1
        flat_args: list[str] = [
            str(entity.version),
            "deleted",
            "1",
            "deleted_at",
            now.isoformat(),
            "version",
            str(new_version),
            "updated_at",
            now.isoformat(),
        ]
        allowed = await self._lock_partial_set_script(keys=[key], args=flat_args)
        if not allowed:
            raise OptimisticLockError(f"Version conflict for entity '{entity_id}': expected {entity.version}")
        await self._append_history(entity)

    async def hard_delete(self, entity_id: str) -> None:
        key = self._make_key(entity_id)
        await self._client.delete(key)
        await self._client.delete(self._history_key(entity_id))
        await self._client.srem(self._index_key, entity_id)

    async def restore(self, entity_id: str) -> T:
        key = self._make_key(entity_id)
        data = await self._client.hgetall(key)
        if not data:
            raise EntityNotFoundError(f"Entity '{entity_id}' not found")
        entity = self._from_hash(data)
        if not entity.deleted:
            raise RepositoryError(f"Entity '{entity_id}' is not deleted")
        now = datetime.now(tz=UTC)
        new_version = entity.version + 1
        flat_args: list[str] = [
            str(entity.version),
            "deleted",
            "0",
            "deleted_at",
            "__NONE__",
            "version",
            str(new_version),
            "updated_at",
            now.isoformat(),
        ]
        allowed = await self._lock_partial_set_script(keys=[key], args=flat_args)
        if not allowed:
            raise OptimisticLockError(f"Version conflict for entity '{entity_id}': expected {entity.version}")
        await self._append_history(entity)
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
            entity = self._from_hash(data)
            if not entity.deleted:
                result.append(entity)
        return result

    async def get_history(self, entity_id: str) -> list[T]:
        history_data = await self._client.lrange(self._history_key(entity_id), 0, -1)
        result = []
        for item in history_data:
            raw = item.decode() if isinstance(item, bytes) else item
            hash_data = json.loads(raw)
            entity = self._from_hash(hash_data)
            result.append(entity)
        return result
