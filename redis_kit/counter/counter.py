from __future__ import annotations

from typing import TYPE_CHECKING

from redis_kit.counter._base import CounterBase, IDGeneratorBase

if TYPE_CHECKING:
    import redis


class BoundCounter:
    """A counter bound to a specific key."""

    def __init__(self, client: redis.Redis, key: str) -> None:
        self._client = client
        self._key = key

    def incr(self, amount: int = 1) -> int:
        return self._client.incrby(self._key, amount)

    def decr(self, amount: int = 1) -> int:
        """Decrement counter. Value can go below zero."""
        return self._client.decrby(self._key, amount)

    def get(self) -> int:
        val = self._client.get(self._key)
        return int(val) if val is not None else 0

    def reset(self) -> None:
        self._client.delete(self._key)


class Counter(CounterBase):
    """Redis-backed counter with transparent key prefixing."""

    def incr(self, name: str, amount: int = 1) -> int:
        return self._client.incrby(self._make_key(name), amount)

    def decr(self, name: str, amount: int = 1) -> int:
        """Decrement counter. Value can go below zero."""
        return self._client.decrby(self._make_key(name), amount)

    def get(self, name: str) -> int:
        val = self._client.get(self._make_key(name))
        return int(val) if val is not None else 0

    def reset(self, name: str) -> None:
        self._client.delete(self._make_key(name))

    def bind(self, name: str) -> BoundCounter:
        return BoundCounter(self._client, self._make_key(name))


class IDGenerator(IDGeneratorBase):
    """Redis-backed atomic ID generator."""

    def next(self) -> int:
        return self._client.incr(self._key)

    def next_str(self) -> str:
        return self._format_id(self.next())
