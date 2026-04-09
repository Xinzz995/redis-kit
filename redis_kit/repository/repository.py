from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar

from redis_kit.exceptions import EntityNotFoundError, OptimisticLockError
from redis_kit.repository._lua import OPTIMISTIC_LOCK_CHECK
from redis_kit.repository.model import BaseModel

if TYPE_CHECKING:
    import redis

T = TypeVar("T", bound=BaseModel)


class Repository:
    """Redis-backed repository with CRUD, versioning, soft delete, and audit."""

    def __init__(self, client: redis.Redis, model_class: type[T], prefix: str = "") -> None:
        self._client = client
        self._model_class = model_class
        self._prefix = prefix
        self._lock_script = self._client.register_script(OPTIMISTIC_LOCK_CHECK)
        self._index_key = f"{self._prefix}:_index" if self._prefix else "_index"

    def _make_key(self, entity_id: str) -> str:
        return f"{self._prefix}:{entity_id}" if self._prefix else entity_id

    def _history_key(self, entity_id: str) -> str:
        return f"{self._make_key(entity_id)}:history"

    def _to_hash(self, entity: BaseModel) -> dict[str, str]:
        result = {}
        for f in dataclasses.fields(entity):
            value = getattr(entity, f.name)
            if value is None:
                result[f.name] = "__NONE__"
            elif isinstance(value, bool):
                result[f.name] = "1" if value else "0"
            elif isinstance(value, datetime):
                result[f.name] = value.isoformat()
            else:
                result[f.name] = str(value)
        return result

    def _from_hash(self, data: dict[bytes | str, bytes | str]) -> T:
        decoded = {}
        for k, v in data.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            decoded[key] = val

        kwargs = {}
        for f in dataclasses.fields(self._model_class):
            raw = decoded.get(f.name)
            if raw is None or raw == "__NONE__":
                kwargs[f.name] = None if raw == "__NONE__" else f.default
            elif f.type in ("int", int):
                kwargs[f.name] = int(raw)
            elif f.type in ("float", float):
                kwargs[f.name] = float(raw)
            elif f.type in ("bool", bool):
                kwargs[f.name] = raw == "1"
            elif f.type in ("datetime | None", "datetime"):
                kwargs[f.name] = datetime.fromisoformat(raw) if raw != "__NONE__" else None
            else:
                kwargs[f.name] = raw
        return self._model_class(**kwargs)

    def save(self, entity: T) -> T:
        now = datetime.now()

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
            # Update existing — optimistic lock check
            key = self._make_key(entity.id)
            allowed = self._lock_script(keys=[key], args=[str(entity.version)])
            if not allowed:
                raise OptimisticLockError(f"Version conflict for entity '{entity.id}': expected {entity.version}")
            # Save current version to history
            existing_data = self._client.hgetall(key)
            if existing_data:
                old_entity = self._from_hash(existing_data)
                history_json = json.dumps(self._to_hash(old_entity))
                self._client.lpush(self._history_key(entity.id), history_json)

            entity = dataclasses.replace(
                entity,
                version=entity.version + 1,
                updated_at=now,
            )

        key = self._make_key(entity.id)
        self._client.hset(key, mapping=self._to_hash(entity))
        self._client.sadd(self._index_key, entity.id)
        return entity

    def find(self, entity_id: str) -> T | None:
        key = self._make_key(entity_id)
        data = self._client.hgetall(key)
        if not data:
            return None
        entity = self._from_hash(data)
        if entity.deleted:
            return None
        return entity

    def find_including_deleted(self, entity_id: str) -> T | None:
        key = self._make_key(entity_id)
        data = self._client.hgetall(key)
        if not data:
            return None
        return self._from_hash(data)

    def delete(self, entity_id: str) -> None:
        key = self._make_key(entity_id)
        data = self._client.hgetall(key)
        if not data:
            raise EntityNotFoundError(f"Entity '{entity_id}' not found")
        now = datetime.now()
        self._client.hset(key, mapping={"deleted": "1", "deleted_at": now.isoformat()})

    def hard_delete(self, entity_id: str) -> None:
        key = self._make_key(entity_id)
        self._client.delete(key)
        self._client.delete(self._history_key(entity_id))
        self._client.srem(self._index_key, entity_id)

    def restore(self, entity_id: str) -> T:
        key = self._make_key(entity_id)
        data = self._client.hgetall(key)
        if not data:
            raise EntityNotFoundError(f"Entity '{entity_id}' not found")
        entity = self._from_hash(data)
        if not entity.deleted:
            raise EntityNotFoundError(f"Entity '{entity_id}' is not deleted")
        self._client.hset(key, mapping={"deleted": "0", "deleted_at": "__NONE__"})
        return dataclasses.replace(entity, deleted=False, deleted_at=None)

    def find_all(self) -> list[T]:
        ids = self._client.smembers(self._index_key)
        result = []
        for raw_id in ids:
            eid = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
            entity = self.find(eid)
            if entity is not None:
                result.append(entity)
        return result

    def get_history(self, entity_id: str) -> list[T]:
        history_data = self._client.lrange(self._history_key(entity_id), 0, -1)
        result = []
        for item in history_data:
            raw = item.decode() if isinstance(item, bytes) else item
            hash_data = json.loads(raw)
            entity = self._from_hash(hash_data)
            result.append(entity)
        return result
