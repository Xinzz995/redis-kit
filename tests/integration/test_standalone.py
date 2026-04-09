from redis_kit.bloom.bloom import BloomFilter
from redis_kit.cache.cache import Cache
from redis_kit.counter.counter import Counter, IDGenerator
from redis_kit.lock.lock import Lock
from redis_kit.queue.delay_queue import DelayQueue
from redis_kit.queue.reliable_queue import ReliableQueue
from redis_kit.ratelimit.sliding_window import SlidingWindowLimiter
from redis_kit.ratelimit.token_bucket import TokenBucketLimiter
from redis_kit.session.session import SessionManager
from redis_kit.stream.consumer import StreamConsumer
from redis_kit.stream.producer import StreamProducer
from tests.integration.conftest import skip_no_redis


@skip_no_redis
class TestCacheIntegration:
    def test_set_get_delete(self, standalone_client):
        cache = Cache(standalone_client, prefix="inttest:cache", ttl_jitter=0)
        cache.set("key1", {"name": "Alice"}, ttl=60)
        assert cache.get("key1") == {"name": "Alice"}
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_get_many_set_many(self, standalone_client):
        cache = Cache(standalone_client, prefix="inttest:cache", ttl_jitter=0)
        cache.set_many({"a": 1, "b": 2, "c": 3}, ttl=60)
        result = cache.get_many(["a", "b", "c", "d"])
        assert result == {"a": 1, "b": 2, "c": 3, "d": None}

    def test_remember(self, standalone_client):
        cache = Cache(standalone_client, prefix="inttest:cache", ttl_jitter=0)
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"val": 42}

        cache.remember("r1", factory, ttl=60)
        cache.remember("r1", factory, ttl=60)
        assert call_count == 1

    def test_ttl_operations(self, standalone_client):
        cache = Cache(standalone_client, prefix="inttest:cache", ttl_jitter=0)
        cache.set("ttlkey", "val", ttl=3600)
        assert cache.ttl("ttlkey") > 3500
        cache.persist("ttlkey")
        assert cache.ttl("ttlkey") == -1
        cache.expire("ttlkey", 600)
        assert 500 < cache.ttl("ttlkey") <= 600


@skip_no_redis
class TestLockIntegration:
    def test_acquire_release(self, standalone_client):
        lock = Lock(standalone_client, prefix="inttest:lock")
        with lock("res-1", timeout=10):
            assert standalone_client.exists("inttest:lock:res-1")
        assert not standalone_client.exists("inttest:lock:res-1")

    def test_reentrant(self, standalone_client):
        lock = Lock(standalone_client, prefix="inttest:lock")
        with lock("res-r", timeout=10, reentrant=True):
            with lock("res-r", timeout=10, reentrant=True):
                pass  # No deadlock


@skip_no_redis
class TestCounterIntegration:
    def test_incr_decr(self, standalone_client):
        c = Counter(standalone_client, prefix="inttest:counter")
        assert c.incr("views") == 1
        assert c.incr("views", 5) == 6
        assert c.decr("views", 2) == 4
        assert c.get("views") == 4

    def test_id_generator(self, standalone_client):
        gen = IDGenerator(standalone_client, "inttest_order", prefix="ORD", padding=8)
        id1 = gen.next_str()
        id2 = gen.next_str()
        assert id1.startswith("ORD")
        assert id2.startswith("ORD")
        assert id1 != id2


@skip_no_redis
class TestBloomIntegration:
    def test_add_exists(self, standalone_client):
        bf = BloomFilter(standalone_client, "inttest_bf", expected_items=1000, false_positive_rate=0.01)
        bf.add("item1")
        assert bf.exists("item1") is True
        assert bf.exists("nonexistent") is False


@skip_no_redis
class TestSessionIntegration:
    def test_crud(self, standalone_client):
        mgr = SessionManager(standalone_client, prefix="inttest:session", ttl=60)
        sid = mgr.create({"user_id": 1, "role": "admin"})
        data = mgr.get(sid)
        assert data["user_id"] == "1"
        mgr.update(sid, {"role": "superadmin"})
        assert mgr.get(sid)["role"] == "superadmin"
        mgr.delete(sid)
        assert mgr.get(sid) is None


@skip_no_redis
class TestQueueIntegration:
    def test_delay_queue(self, standalone_client):
        dq = DelayQueue(standalone_client, "inttest_dq")
        dq.put({"task": "test"}, delay=0)
        msgs = dq.poll(count=10)
        assert len(msgs) == 1
        assert msgs[0]["task"] == "test"

    def test_reliable_queue(self, standalone_client):
        rq = ReliableQueue(standalone_client, "inttest_rq")
        rq.put({"task": "email"})
        msg = rq.get()
        assert msg.data["task"] == "email"
        msg.ack()
        assert rq.processing_count() == 0


@skip_no_redis
class TestRateLimitIntegration:
    def test_token_bucket(self, standalone_client):
        limiter = TokenBucketLimiter(standalone_client, rate=10, capacity=5, prefix="inttest:rl:tb")
        result = limiter.acquire("user1")
        assert result.allowed is True

    def test_sliding_window(self, standalone_client):
        limiter = SlidingWindowLimiter(standalone_client, limit=5, window=60, prefix="inttest:rl:sw")
        result = limiter.acquire("user1")
        assert result.allowed is True
        assert result.remaining == 4


@skip_no_redis
class TestStreamIntegration:
    def test_produce_consume(self, standalone_client):
        producer = StreamProducer(standalone_client, stream="inttest_stream")
        producer.add({"key": "val1"})
        producer.add({"key": "val2"})
        assert producer.len() == 2

        consumer = StreamConsumer(
            standalone_client,
            stream="inttest_stream",
            group="inttest_g",
            consumer_name="w1",
            auto_ack=True,
        )
        consumer.ensure_group()
        messages = list(consumer.listen(count=10, block=0))
        assert len(messages) == 2
        assert messages[0].data["key"] == "val1"
