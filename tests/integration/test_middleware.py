import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from fastapicap import (
    RateLimiter,
    GCRARateLimiter,
    SlidingWindowRateLimiter,
    SlidingWindowLogRateLimiter,
    LeakyBucketRateLimiter,
    TokenBucketRateLimiter,
)
from fastapicap.middleware import RateLimitMiddleware, RateLimitConfig


@pytest_asyncio.fixture
def app_factory():
    def _create_app(limiter):
        app = FastAPI()

        # Add middleware with /excluded route excluded
        app.add_middleware(
            RateLimitMiddleware,
            limiters=[limiter],
            config=RateLimitConfig(enabled=True),
            exclude_paths=["/excluded"],
        )

        @app.get("/ping")
        async def ping():
            return {"message": "pong"}

        @app.get("/excluded")
        async def excluded():
            return {"message": "this route is excluded from rate limiting"}

        return app

    return _create_app


@pytest.mark.asyncio
async def test_fixed_window_rate_limiter(app_factory):
    limiter = RateLimiter(limit=3, seconds=10)
    app = app_factory(limiter)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Make 5 requests to /ping
        ping_responses = []
        for _ in range(5):
            res = await client.get("/ping")
            ping_responses.append(res)

        # First 3 should succeed
        assert ping_responses[0].status_code == 200
        assert ping_responses[1].status_code == 200
        assert ping_responses[2].status_code == 200

        # 4th and 5th should be rate-limited
        assert ping_responses[3].status_code == 429
        assert ping_responses[4].status_code == 429
        assert "Retry-After" in ping_responses[3].headers

        # Now hit the excluded route multiple times
        for _ in range(5):
            excluded_response = await client.get("/excluded")
            assert excluded_response.status_code == 200
            assert excluded_response.json() == {
                "message": "this route is excluded from rate limiting"
            }


@pytest.mark.asyncio
async def test_gcra_limiter(app_factory):
    limiter = GCRARateLimiter(burst=3, tokens_per_second=1)
    app = app_factory(limiter)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for i in range(3):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Request {i + 1} should succeed"

        res4 = await client.get("/ping")
        assert res4.status_code == 429
        assert "Retry-After" in res4.headers

        # Wait for token refill (3 seconds → 3 tokens should refill)
        await asyncio.sleep(3.1)
        for i in range(3):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Refilled request {i + 1} should succeed"

        # Another burst again immediately should hit limit
        res = await client.get("/ping")
        assert res.status_code == 429

        # Test For Excluded Routes
        for _ in range(5):
            excluded_response = await client.get("/excluded")
            assert excluded_response.status_code == 200
            assert excluded_response.json() == {
                "message": "this route is excluded from rate limiting"
            }


@pytest.mark.asyncio
async def test_sliding_window_limiter(app_factory):
    limiter = SlidingWindowRateLimiter(limit=10, seconds=2)
    app = app_factory(limiter)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Phase 1: Exhaust the limit in the first window.
        # All 10 requests should pass.
        for i in range(10):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Request {i + 1} should pass"

        # Next request should be rate-limited
        res = await client.get("/ping")
        assert res.status_code == 429, "11th request should be rate-limited"
        assert "Retry-After" in res.headers

        #  Excluded path bypasses limiter
        for _ in range(5):
            excluded = await client.get("/excluded")
            assert excluded.status_code == 200
            assert excluded.json() == {
                "message": "this route is excluded from rate limiting"
            }


@pytest.mark.asyncio
async def test_sliding_log_limiter(app_factory):
    limiter = SlidingWindowLogRateLimiter(limit=5, window_seconds=6)
    app = app_factory(limiter)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Phase 1: Fill the rate limit with short spacing
        for i in range(5):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Initial request {i + 1} should succeed"
            await asyncio.sleep(0.2)  # Short gap between requests

        # 6th request should be blocked
        res = await client.get("/ping")
        assert res.status_code == 429, "6th request should be rate-limited"
        assert "Retry-After" in res.headers

        # Phase 2: Wait for full window expiration
        await asyncio.sleep(6)

        # Now all 5 requests should succeed again
        for i in range(5):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Request {i + 1} after decay should pass"

        # Excluded route must bypass limiter
        for _ in range(3):
            res = await client.get("/excluded")
            assert res.status_code == 200
            assert res.json() == {
                "message": "this route is excluded from rate limiting"
            }


@pytest.mark.asyncio
async def test_leaky_bucket_limiter(app_factory):
    limiter = LeakyBucketRateLimiter(capacity=5, leaks_per_second=1)
    app = app_factory(limiter)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Phase 1: Fill the bucket — all should pass
        for i in range(5):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Request {i + 1} should succeed"
            await asyncio.sleep(0.1)

        # 6th request must be rejected
        res = await client.get("/ping")
        assert res.status_code == 429, "6th request should be throttled"
        assert "Retry-After" in res.headers
        retry_after = int(res.headers["Retry-After"])
        assert 1 <= retry_after <= 5, f"Retry-After should be 1-5, got {retry_after}"

        # Phase 2: Wait for 3 seconds (3 slots should leak out)
        await asyncio.sleep(3.1)

        # Now at least 2-3 requests should pass again
        allowed = 0
        for _ in range(5):
            res = await client.get("/ping")
            if res.status_code == 200:
                allowed += 1
            else:
                break

        assert 2 <= allowed <= 3, f"Expected 2–3 allowed after 3s decay, got {allowed}"

        # Phase 3: Wait for full drain
        await asyncio.sleep(5)

        # Bucket should be reset
        for i in range(5):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Post-reset request {i + 1} should succeed"

        # Excluded paths must not be limited
        for _ in range(6):
            res = await client.get("/excluded")
            assert res.status_code == 200
            assert res.json() == {
                "message": "this route is excluded from rate limiting"
            }


@pytest.mark.asyncio
async def test_token_bucket_limiter(app_factory):
    limiter = TokenBucketRateLimiter(capacity=5, tokens_per_second=1)
    app = app_factory(limiter)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Phase 1: Fill capacity
        for i in range(5):
            res = await client.get("/ping")
            assert res.status_code == 200, f"Request {i + 1} should succeed"

        # Should now be rate limited (bucket empty)
        res = await client.get("/ping")
        assert res.status_code == 429, "Bucket should be empty — rate limited"
        assert "Retry-After" in res.headers

        # Phase 2: Wait for refill (2 seconds = 2 tokens)
        await asyncio.sleep(2.1)

        allowed = 0
        for _ in range(5):
            res = await client.get("/ping")
            if res.status_code == 200:
                allowed += 1
            else:
                break

        assert 2 <= allowed <= 3, f"Expected 2-3 allowed after refill, got {allowed}"

        # Wait again to refill fully
        await asyncio.sleep(5.1)

        for i in range(5):
            res = await client.get("/ping")
            assert res.status_code == 200, (
                f"Request {i + 1} after full refill should succeed"
            )
            await asyncio.sleep(0.05)

        # Excluded route (if any)
        for _ in range(3):
            res = await client.get("/excluded")
            assert res.status_code == 200
            assert res.json() == {
                "message": "this route is excluded from rate limiting"
            }
