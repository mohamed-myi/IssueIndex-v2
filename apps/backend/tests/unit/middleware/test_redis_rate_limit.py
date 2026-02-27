

import fakeredis.aioredis
import pytest

from gim_backend.middleware.rate_limit import (
    RedisRateLimiter,
    _build_compound_key,
)


@pytest.fixture
async def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def redis_limiter(fake_redis):
    return RedisRateLimiter(fake_redis)


class TestRedisRateLimiterSequence:

    @pytest.mark.asyncio
    async def test_expire_set_immediately_after_first_incr(self, fake_redis, redis_limiter):

        await redis_limiter.is_rate_limited("test_key", max_requests=10, window_seconds=60)


        ttl = await fake_redis.ttl("rate_limit:test_key")

        assert ttl > 0, "TTL must be set after first request"
        assert ttl <= 60, f"TTL should be <= 60 seconds, got {ttl}"

    @pytest.mark.asyncio
    async def test_incr_is_atomic_count_matches_requests(self, fake_redis, redis_limiter):
        for i in range(5):
            await redis_limiter.is_rate_limited("atomic_test", max_requests=10, window_seconds=60)


        count = await fake_redis.get("rate_limit:atomic_test")

        assert int(count) == 5, f"After 5 requests, count should be 5, got {count}"

    @pytest.mark.asyncio
    async def test_rate_limit_triggers_at_correct_threshold(self, redis_limiter):
        results = []
        for i in range(12):
            is_limited, _ = await redis_limiter.is_rate_limited("threshold_test", max_requests=10, window_seconds=60)
            results.append((i + 1, is_limited))


        for req_num, is_limited in results[:10]:
            assert is_limited is False, f"Request {req_num} should NOT be limited"


        for req_num, is_limited in results[10:]:
            assert is_limited is True, f"Request {req_num} SHOULD be limited"

    @pytest.mark.asyncio
    async def test_retry_after_matches_actual_ttl(self, fake_redis, redis_limiter):

        for _ in range(10):
            await redis_limiter.is_rate_limited("ttl_test", max_requests=10, window_seconds=60)


        is_limited, retry_after = await redis_limiter.is_rate_limited("ttl_test", max_requests=10, window_seconds=60)


        actual_ttl = await fake_redis.ttl("rate_limit:ttl_test")

        assert is_limited is True

        assert abs(retry_after - actual_ttl) <= 1, f"retry_after ({retry_after}) should match TTL ({actual_ttl})"

    @pytest.mark.asyncio
    async def test_different_keys_are_isolated(self, redis_limiter):

        for _ in range(10):
            await redis_limiter.is_rate_limited("key_a", max_requests=10, window_seconds=60)

        limited_a, _ = await redis_limiter.is_rate_limited("key_a", max_requests=10, window_seconds=60)
        limited_b, _ = await redis_limiter.is_rate_limited("key_b", max_requests=10, window_seconds=60)

        assert limited_a is True, "key_a should be rate limited"
        assert limited_b is False, "key_b should NOT be rate limited"

    @pytest.mark.asyncio
    async def test_expire_not_reset_on_subsequent_requests(self, fake_redis, redis_limiter):

        await redis_limiter.is_rate_limited("ttl_reset", max_requests=10, window_seconds=60)
        initial_ttl = await fake_redis.ttl("rate_limit:ttl_reset")


        for _ in range(5):
            await redis_limiter.is_rate_limited("ttl_reset", max_requests=10, window_seconds=60)


        final_ttl = await fake_redis.ttl("rate_limit:ttl_reset")


        assert final_ttl <= initial_ttl, "TTL should not increase on subsequent requests"


class TestRedisRateLimiterClear:

    @pytest.mark.asyncio
    async def test_clear_specific_key(self, fake_redis, redis_limiter):

        await redis_limiter.is_rate_limited("keep_me", max_requests=10, window_seconds=60)
        await redis_limiter.is_rate_limited("delete_me", max_requests=10, window_seconds=60)


        await redis_limiter.clear("delete_me")


        kept = await fake_redis.exists("rate_limit:keep_me")
        deleted = await fake_redis.exists("rate_limit:delete_me")

        assert kept == 1, "keep_me should still exist"
        assert deleted == 0, "delete_me should be gone"


class TestCompoundKeyNonRegression:

    def test_compound_key_with_flow_id(self):
        key = _build_compound_key("192.168.1.1", "flow_abc")
        assert key == "192.168.1.1:flow_abc"

    def test_compound_key_without_flow_id(self):
        key = _build_compound_key("192.168.1.1", None)
        assert key == "192.168.1.1"

    def test_different_flows_produce_different_keys(self):
        key_a = _build_compound_key("192.168.1.1", "flow_a")
        key_b = _build_compound_key("192.168.1.1", "flow_b")

        assert key_a != key_b
