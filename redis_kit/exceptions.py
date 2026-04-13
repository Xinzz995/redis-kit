from __future__ import annotations

from typing import Any

# --- Base ---


class RedisKitError(Exception):
    """Base exception for all redis-kit errors."""


# --- Connection ---


class RedisConnectionError(RedisKitError):
    """Redis connection failed."""


class ConnectionPoolExhaustedError(RedisConnectionError):
    """No available connections in the pool."""


# --- Serialization ---


class SerializationError(RedisKitError):
    """Serialization or deserialization failed."""


# --- Lock ---


class LockError(RedisKitError):
    """Base lock error."""


class LockAcquireError(LockError):
    """Failed to acquire a lock."""


class LockReleaseError(LockError):
    """Failed to release a lock."""


# --- Cache ---


class CacheError(RedisKitError):
    """Cache operation failed."""


# --- Queue ---


class QueueError(RedisKitError):
    """Queue operation failed."""


class QueueEmptyError(QueueError):
    """Queue is empty."""


# --- Bloom ---


class BloomFilterError(RedisKitError):
    """Bloom filter operation failed."""


# --- Session ---


class SessionError(RedisKitError):
    """Session operation failed."""


class SessionNotFoundError(SessionError):
    """Session does not exist or has expired."""


# --- Topology ---


class TopologyConstraintError(RedisKitError):
    """Operation not supported under current topology (e.g., cross-slot in Cluster)."""


# --- Repository ---


class RepositoryError(RedisKitError):
    """Repository operation failed."""


class EntityNotFoundError(RepositoryError):
    """Entity does not exist."""


class OptimisticLockError(RepositoryError):
    """Version conflict during save."""


# --- Fallback Policy ---
# FallbackPolicy lives in redis_kit.policy; re-exported here for backwards compatibility.
from redis_kit.policy import FallbackPolicy  # noqa: F401


# --- Stream ---


class StreamError(RedisKitError):
    """Stream operation failed."""


# --- Rate Limit ---


class RateLimitExceeded(RedisKitError):
    """Rate limit exceeded."""

    def __init__(self, result: Any) -> None:
        self.result = result
        super().__init__(
            f"Rate limit exceeded: {result.remaining}/{result.limit}, retry after {result.retry_after:.1f}s"
        )
