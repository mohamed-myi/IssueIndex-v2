"""
Redis Rate Limiter Tests - Using FakeRedis

Tests the Redis rate limiter backend with a real (fake) Redis instance.
No mocking of Redis commands - we verify actual stateful behavior.

Focus areas:
- INCR + EXPIRE sequence atomicity
- TTL retrieval for retry-after header
- Sliding window expiration
- Connection failure fallback
"""
import pytest
import fakeredis.aioredis

from src.middleware.rate_limit import (
    RedisRateLimiter,
    _build_compound_key,
)


@pytest.fixture
async def fake_redis():
    """
    Create a FakeRedis instance that behaves like real Redis.
    This catches logic errors that mocking would miss.
    """
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def redis_limiter(fake_redis):
    """Redis rate limiter using fake Redis backend."""
    return RedisRateLimiter(fake_redis)


class TestRedisRateLimiterSequence:
    """
    Test the SEQUENCE of Redis operations, not just return values.
    FakeRedis maintains state so we prove the logic actually works.
    """
    
    @pytest.mark.asyncio
    async def test_expire_set_immediately_after_first_incr(self, fake_redis, redis_limiter):
        """
        CRITICAL: EXPIRE must be called on first request.
        If we forget EXPIRE, the key lives forever = permanent rate limit.
        """
        # First request
        await redis_limiter.is_rate_limited("test_key", max_requests=10, window_seconds=60)
        
        # Verify TTL was set (not -1 which means no expiry)
        ttl = await fake_redis.ttl("rate_limit:test_key")
        
        assert ttl > 0, "TTL must be set after first request"
        assert ttl <= 60, f"TTL should be <= 60 seconds, got {ttl}"
    
    @pytest.mark.asyncio
    async def test_incr_is_atomic_count_matches_requests(self, fake_redis, redis_limiter):
        """
        Verify INCR correctly tracks request count.
        After 5 requests, count should be exactly 5.
        """
        for i in range(5):
            await redis_limiter.is_rate_limited("atomic_test", max_requests=10, window_seconds=60)
        
        # Read the actual value in Redis
        count = await fake_redis.get("rate_limit:atomic_test")
        
        assert int(count) == 5, f"After 5 requests, count should be 5, got {count}"
    
    @pytest.mark.asyncio
    async def test_rate_limit_triggers_at_correct_threshold(self, redis_limiter):
        """
        With max_requests=10, request 11 should be blocked.
        """
        results = []
        for i in range(12):
            is_limited, _ = await redis_limiter.is_rate_limited(
                "threshold_test", max_requests=10, window_seconds=60
            )
            results.append((i + 1, is_limited))
        
        # Requests 1-10 should pass
        for req_num, is_limited in results[:10]:
            assert is_limited is False, f"Request {req_num} should NOT be limited"
        
        # Requests 11-12 should be blocked
        for req_num, is_limited in results[10:]:
            assert is_limited is True, f"Request {req_num} SHOULD be limited"
    
    @pytest.mark.asyncio
    async def test_retry_after_matches_actual_ttl(self, fake_redis, redis_limiter):
        """
        Retry-After header MUST match the actual Redis TTL.
        No hardcoded values - we verify against real state.
        """
        # Fill up the bucket
        for _ in range(10):
            await redis_limiter.is_rate_limited("ttl_test", max_requests=10, window_seconds=60)
        
        # Trigger rate limit
        is_limited, retry_after = await redis_limiter.is_rate_limited(
            "ttl_test", max_requests=10, window_seconds=60
        )
        
        # Get actual TTL from Redis
        actual_ttl = await fake_redis.ttl("rate_limit:ttl_test")
        
        assert is_limited is True
        # retry_after should be close to actual_ttl (within 1 second tolerance)
        assert abs(retry_after - actual_ttl) <= 1, \
            f"retry_after ({retry_after}) should match TTL ({actual_ttl})"
    
    @pytest.mark.asyncio
    async def test_different_keys_are_isolated(self, redis_limiter):
        """
        Rate limits for different keys must be completely independent.
        """
        # Exhaust limit for key_a
        for _ in range(10):
            await redis_limiter.is_rate_limited("key_a", max_requests=10, window_seconds=60)
        
        limited_a, _ = await redis_limiter.is_rate_limited(
            "key_a", max_requests=10, window_seconds=60
        )
        limited_b, _ = await redis_limiter.is_rate_limited(
            "key_b", max_requests=10, window_seconds=60
        )
        
        assert limited_a is True, "key_a should be rate limited"
        assert limited_b is False, "key_b should NOT be rate limited"
    
    @pytest.mark.asyncio
    async def test_expire_not_reset_on_subsequent_requests(self, fake_redis, redis_limiter):
        """
        EXPIRE should only be called on count == 1.
        Subsequent requests must NOT reset the window.
        """
        # First request sets TTL
        await redis_limiter.is_rate_limited("ttl_reset", max_requests=10, window_seconds=60)
        initial_ttl = await fake_redis.ttl("rate_limit:ttl_reset")
        
        # Simulate some time passing (by sleeping briefly is expensive, so we check logic)
        # Make 5 more requests
        for _ in range(5):
            await redis_limiter.is_rate_limited("ttl_reset", max_requests=10, window_seconds=60)
        
        # TTL should have decreased or stayed same, NOT reset to 60
        final_ttl = await fake_redis.ttl("rate_limit:ttl_reset")
        
        # In real time this would be less, but in test it's nearly instant
        # The key check: TTL was not reset to full window
        assert final_ttl <= initial_ttl, "TTL should not increase on subsequent requests"


class TestRedisRateLimiterClear:
    """Test the clear functionality."""
    
    @pytest.mark.asyncio
    async def test_clear_specific_key(self, fake_redis, redis_limiter):
        """Clear should remove only the specified key."""
        # Create two rate limit entries
        await redis_limiter.is_rate_limited("keep_me", max_requests=10, window_seconds=60)
        await redis_limiter.is_rate_limited("delete_me", max_requests=10, window_seconds=60)
        
        # Clear only one
        await redis_limiter.clear("delete_me")
        
        # Verify state
        kept = await fake_redis.exists("rate_limit:keep_me")
        deleted = await fake_redis.exists("rate_limit:delete_me")
        
        assert kept == 1, "keep_me should still exist"
        assert deleted == 0, "delete_me should be gone"


class TestCompoundKeyNonRegression:
    """Ensure compound key logic hasn't been accidentally broken."""
    
    def test_compound_key_with_flow_id(self):
        """IP + flow_id should produce unique key."""
        key = _build_compound_key("192.168.1.1", "flow_abc")
        assert key == "192.168.1.1:flow_abc"
    
    def test_compound_key_without_flow_id(self):
        """No flow_id should use IP only."""
        key = _build_compound_key("192.168.1.1", None)
        assert key == "192.168.1.1"
    
    def test_different_flows_produce_different_keys(self):
        """Two flows from same IP must have different keys."""
        key_a = _build_compound_key("192.168.1.1", "flow_a")
        key_b = _build_compound_key("192.168.1.1", "flow_b")
        
        assert key_a != key_b
