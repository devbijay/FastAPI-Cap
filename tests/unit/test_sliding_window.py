import asyncio
import pytest
from fastapicap import SlidingWindowRateLimiter


class DummyRequest:
    def __init__(self, path="/test", ip="1.2.3.4"):
        self.headers = {}
        self.client = type("client", (), {"host": ip})()
        self.url = type("url", (), {"path": path})()


class DummyResponse:
    pass


@pytest.mark.asyncio
async def test_sliding_window_allows_within_limit(redis_ready):
    limiter = SlidingWindowRateLimiter(limit=2, seconds=3)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)
    await limiter(request, response)  # Should not raise


@pytest.mark.asyncio
async def test_sliding_window_blocks_over_limit(redis_ready):
    limiter = SlidingWindowRateLimiter(limit=2, seconds=3)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)
    await limiter(request, response)
    with pytest.raises(Exception) as excinfo:
        await limiter(request, response)
    assert "Rate limit exceeded" in str(excinfo.value)


@pytest.mark.asyncio
async def test_sliding_window_separate_keys(redis_ready):
    limiter = SlidingWindowRateLimiter(limit=1, seconds=3)
    req1 = DummyRequest(path="/test1", ip="1.2.3.4")
    req2 = DummyRequest(path="/test2", ip="1.2.3.4")
    response = DummyResponse()
    await limiter(req1, response)  # Allowed
    await limiter(req2, response)  # Allowed (different key)
    with pytest.raises(Exception):
        await limiter(req1, response)  # Blocked for /test1


@pytest.mark.asyncio
async def test_sliding_window_resets_after_window(redis_ready):
    limiter = SlidingWindowRateLimiter(limit=1, seconds=3)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)  # Allowed
    with pytest.raises(Exception):
        await limiter(request, response)  # Blocked

    # Sliding Window => Gradual weighted Reset Behavior, => Test Wait Needed 2 windows (to be sure)
    await asyncio.sleep(6.2)  # Wait for 2 window to reset
    await limiter(request, response)  # Allowed again


@pytest.mark.asyncio
async def test_sliding_window_different_ips(redis_ready):
    limiter = SlidingWindowRateLimiter(limit=1, seconds=3)
    req1 = DummyRequest(ip="1.2.3.4")
    req2 = DummyRequest(ip="5.6.7.8")
    response = DummyResponse()
    await limiter(req1, response)  # Allowed
    await limiter(req2, response)  # Allowed (different IP)
    with pytest.raises(Exception):
        await limiter(req1, response)  # Blocked for 1.2.3.4


@pytest.mark.asyncio
async def test_sliding_window_custom_key_func(redis_ready):
    async def custom_key_func(request):
        return "custom"

    limiter = SlidingWindowRateLimiter(limit=1, seconds=3, key_func=custom_key_func)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)  # Allowed
    with pytest.raises(Exception):
        await limiter(request, response)  # Blocked


@pytest.mark.asyncio
async def test_sliding_window_custom_on_limit(redis_ready):
    called = {}

    async def custom_on_limit(request, response, retry_after):
        called["hit"] = True
        raise Exception("Custom limit hit")

    limiter = SlidingWindowRateLimiter(limit=1, seconds=3, on_limit=custom_on_limit)
    request = DummyRequest()
    response = DummyResponse()
    await limiter(request, response)  # Allowed
    with pytest.raises(Exception) as excinfo:
        await limiter(request, response)
    assert "Custom limit hit" in str(excinfo.value)
    assert called["hit"]


@pytest.mark.asyncio
async def test_sliding_window_prefix_isolation(redis_ready):
    limiter1 = SlidingWindowRateLimiter(limit=1, seconds=3, prefix="a")
    limiter2 = SlidingWindowRateLimiter(limit=1, seconds=3, prefix="b")
    request = DummyRequest()
    response = DummyResponse()
    await limiter1(request, response)  # Allowed
    await limiter2(request, response)  # Allowed (different prefix)
    with pytest.raises(Exception):
        await limiter1(request, response)  # Blocked for prefix "a"
    with pytest.raises(Exception):
        await limiter2(request, response)  # Blocked for prefix "b"
