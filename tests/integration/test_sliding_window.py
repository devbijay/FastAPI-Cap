import asyncio
import pytest
from httpx import ASGITransport
from fastapi import FastAPI, Depends
from fastapicap import SlidingWindowRateLimiter
import httpx

# --- App fixture for each test ---


@pytest.fixture
def app():
    app = FastAPI()
    limiter = SlidingWindowRateLimiter(limit=2, seconds=3)

    @app.get("/ping", dependencies=[Depends(limiter)])
    async def ping():
        return {"message": "pong"}

    @app.get("/hello", dependencies=[Depends(limiter)])
    async def hello():
        return {"message": "hello"}

    return app


# --- Integration tests for SlidingWindowRateLimiter ---


@pytest.mark.asyncio
async def test_sliding_window_allows_within_limit(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.get("/ping")
        assert r1.status_code == 200
        r2 = await client.get("/ping")
        assert r2.status_code == 200


@pytest.mark.asyncio
async def test_sliding_window_blocks_over_limit(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/ping")
        await client.get("/ping")
        r3 = await client.get("/ping")
        assert r3.status_code == 429
        assert "Rate limit exceeded" in r3.text


@pytest.mark.asyncio
async def test_sliding_window_resets_after_window(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/ping")).status_code == 200
        assert (await client.get("/ping")).status_code == 200
        r3 = await client.get("/ping")
        assert r3.status_code == 429
        await asyncio.sleep(6.1)
        assert (await client.get("/ping")).status_code == 200


@pytest.mark.asyncio
async def test_sliding_window_separate_keys(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/ping")).status_code == 200
        assert (await client.get("/hello")).status_code == 200
        assert (await client.get("/ping")).status_code == 200  # Should be 200!
        assert (await client.get("/ping")).status_code == 429  # Now this should be 429


@pytest.mark.asyncio
async def test_sliding_window_multiple_limiters():
    app = FastAPI()
    limiter1 = SlidingWindowRateLimiter(limit=1, seconds=3, prefix="short")
    limiter2 = SlidingWindowRateLimiter(limit=2, seconds=5, prefix="long")

    @app.get("/multi", dependencies=[Depends(limiter1), Depends(limiter2)])
    async def multi():
        return {"message": "multi-limited"}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # First request: both limiters allow
        assert (await client.get("/multi")).status_code == 200
        # Second request: limiter1 should block, limiter2 is NOT called
        r2 = await client.get("/multi")
        assert r2.status_code == 429
        # Wait for limiter1 window to reset
        await asyncio.sleep(6.1)
        # Third request: limiter1 allows, limiter2 allows (counter=2)
        r3 = await client.get("/multi")
        assert r3.status_code == 200
        # Fourth request: limiter1 allows, limiter2 blocks (counter=3, limit=2)
        r4 = await client.get("/multi")
        assert r4.status_code == 429
