import logging

import pytest

from redis_kit.exceptions import (
    BloomFilterError,
    CacheError,
    ConnectionPoolExhaustedError,
    FallbackPolicy,
    LockAcquireError,
    LockError,
    LockReleaseError,
    QueueEmptyError,
    QueueError,
    RedisConnectionError,
    RedisKitError,
    SerializationError,
    SessionError,
    SessionNotFoundError,
)


class TestExceptionHierarchy:
    def test_base_exception(self):
        with pytest.raises(RedisKitError):
            raise RedisKitError("test")

    def test_connection_error_inherits(self):
        with pytest.raises(RedisKitError):
            raise RedisConnectionError("conn failed")

    def test_pool_exhausted_inherits(self):
        with pytest.raises(RedisConnectionError):
            raise ConnectionPoolExhaustedError("no connections")

    def test_serialization_error(self):
        with pytest.raises(RedisKitError):
            raise SerializationError("bad data")

    def test_lock_hierarchy(self):
        with pytest.raises(LockError):
            raise LockAcquireError("timeout")
        with pytest.raises(LockError):
            raise LockReleaseError("not owner")

    def test_cache_error(self):
        with pytest.raises(RedisKitError):
            raise CacheError("cache fail")

    def test_queue_hierarchy(self):
        with pytest.raises(QueueError):
            raise QueueEmptyError("empty")

    def test_bloom_error(self):
        with pytest.raises(RedisKitError):
            raise BloomFilterError("bloom fail")

    def test_session_hierarchy(self):
        with pytest.raises(SessionError):
            raise SessionNotFoundError("not found")

    def test_exception_with_context(self):
        original = ValueError("original")
        err = CacheError("cache fail")
        err.__cause__ = original
        assert err.__cause__ is original


class TestFallbackPolicy:
    def test_default_raise(self):
        policy = FallbackPolicy()
        assert policy.on_connection_error == "raise"
        assert policy.fallback is None
        assert policy.log_on_fallback is True

    def test_return_none(self):
        policy = FallbackPolicy(on_connection_error="return_none")
        assert policy.on_connection_error == "return_none"

    def test_callback(self):
        def my_fallback():
            return "default"

        policy = FallbackPolicy(on_connection_error="callback", fallback=my_fallback)
        assert policy.fallback is not None
        assert policy.fallback() == "default"

    def test_custom_logger(self):
        logger = logging.getLogger("custom")
        policy = FallbackPolicy(logger=logger)
        assert policy.logger is logger

    def test_default_logger(self):
        policy = FallbackPolicy()
        assert policy.logger.name == "redis_kit"
