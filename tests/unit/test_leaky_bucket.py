import pytest
from fastapicap import LeakyBucketRateLimiter


class DummyRequest:
    def __init__(self, path="/test", ip="1.2.3.4"):
        self.headers = {}
        self.client = type("client", (), {"host": ip})()
        self.url = type("url", (), {"path": path})()


class DummyResponse:
    pass


@pytest.mark.asyncio
async def test_leaky_bucket_allows_within_capacity(redis_ready):
    limiter = LeakyBucketRateLimiter(capacity=2, leaks_per_second=0)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)
    await limiter(request, response)  # Should not raise


@pytest.mark.asyncio
async def test_leaky_bucket_blocks_when_full(redis_ready):
    limiter = LeakyBucketRateLimiter(capacity=2, leaks_per_second=0)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)
    await limiter(request, response)
    with pytest.raises(Exception) as excinfo:
        await limiter(request, response)
    assert "Rate limit exceeded" in str(excinfo.value)


@pytest.mark.asyncio
async def test_leaky_bucket_leaks(redis_ready):
    limiter = LeakyBucketRateLimiter(capacity=1, leaks_per_second=1)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)  # Use up the only slot

    # Immediately try again, should be blocked
    with pytest.raises(Exception):
        await limiter(request, response)

    # Wait for 1.1 seconds for a slot to leak out
    import asyncio

    await asyncio.sleep(1.1)
    await limiter(request, response)  # Should be allowed again


@pytest.mark.asyncio
async def test_leaky_bucket_separate_keys(redis_ready):
    limiter = LeakyBucketRateLimiter(capacity=1, leaks_per_second=0)
    req1 = DummyRequest(path="/test1", ip="1.2.3.4")
    req2 = DummyRequest(path="/test2", ip="1.2.3.4")
    response = DummyResponse()
    await limiter(req1, response)  # Allowed
    await limiter(req2, response)  # Allowed (different key)
    with pytest.raises(Exception):
        await limiter(req1, response)  # Blocked for /test1


@pytest.mark.asyncio
async def test_leaky_bucket_different_ips(redis_ready):
    limiter = LeakyBucketRateLimiter(capacity=1, leaks_per_second=0)
    req1 = DummyRequest(ip="1.2.3.4")
    req2 = DummyRequest(ip="5.6.7.8")
    response = DummyResponse()
    await limiter(req1, response)  # Allowed
    await limiter(req2, response)  # Allowed (different IP)
    with pytest.raises(Exception):
        await limiter(req1, response)  # Blocked for 1.2.3.4


@pytest.mark.asyncio
async def test_leaky_bucket_custom_key_func(redis_ready):
    async def custom_key_func(request):
        return "custom"

    limiter = LeakyBucketRateLimiter(
        capacity=1, leaks_per_second=0, key_func=custom_key_func
    )
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)  # Allowed
    with pytest.raises(Exception):
        await limiter(request, response)  # Blocked


@pytest.mark.asyncio
async def test_leaky_bucket_custom_on_limit(redis_ready):
    called = {}

    async def custom_on_limit(request, response, retry_after):
        called["hit"] = True
        raise Exception("Custom limit hit")

    limiter = LeakyBucketRateLimiter(
        capacity=1, leaks_per_second=0, on_limit=custom_on_limit
    )
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)  # Allowed
    with pytest.raises(Exception) as excinfo:
        await limiter(request, response)
    assert "Custom limit hit" in str(excinfo.value)
    assert called["hit"]


@pytest.mark.asyncio
async def test_leaky_bucket_prefix_isolation(redis_ready):
    limiter1 = LeakyBucketRateLimiter(capacity=1, leaks_per_second=0, prefix="a")
    limiter2 = LeakyBucketRateLimiter(capacity=1, leaks_per_second=0, prefix="b")
    request = DummyRequest()
    response = DummyResponse()
    await limiter1(request, response)  # Allowed
    await limiter2(request, response)  # Allowed (different prefix)
    with pytest.raises(Exception):
        await limiter1(request, response)  # Blocked for prefix "a"
    with pytest.raises(Exception):
        await limiter2(request, response)  # Blocked for prefix "b"


@pytest.mark.asyncio
async def test_leaky_bucket_multiple_limiters(redis_ready):
    limiter1 = LeakyBucketRateLimiter(capacity=1, leaks_per_second=0)
    limiter2 = LeakyBucketRateLimiter(capacity=2, leaks_per_second=0)
    request = DummyRequest()
    response = DummyResponse()
    await limiter1(request, response)  # Allowed
    await limiter2(request, response)  # Allowed
    await limiter2(request, response)  # Allowed (second slot)
    with pytest.raises(Exception):
        await limiter1(request, response)  # Blocked for limiter1
    with pytest.raises(Exception):
        await limiter2(request, response)  # Blocked for limiter2
