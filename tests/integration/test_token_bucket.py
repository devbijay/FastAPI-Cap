import asyncio
import pytest
from fastapi import FastAPI, Depends
from httpx import ASGITransport
import httpx

from fastapicap import TokenBucketRateLimiter


@pytest.fixture
def app():
    app = FastAPI()
    limiter = TokenBucketRateLimiter(capacity=2, tokens_per_second=1)

    @app.get("/ping", dependencies=[Depends(limiter)])
    async def ping():
        return {"message": "pong"}

    @app.get("/hello", dependencies=[Depends(limiter)])
    async def hello():
        return {"message": "hello"}

    return app


@pytest.mark.asyncio
async def test_token_bucket_allows_within_capacity(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/ping")).status_code == 200
        assert (await client.get("/ping")).status_code == 200


@pytest.mark.asyncio
async def test_token_bucket_blocks_when_empty(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/ping")
        await client.get("/ping")
        r3 = await client.get("/ping")
        assert r3.status_code == 429
        assert "Rate limit exceeded" in r3.text


@pytest.mark.asyncio
async def test_token_bucket_refills(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/ping")
        await client.get("/ping")
        r3 = await client.get("/ping")
        assert r3.status_code == 429
        await asyncio.sleep(1.1)  # Wait for 1 token to refill
        r4 = await client.get("/ping")
        assert r4.status_code == 200


@pytest.mark.asyncio
async def test_token_bucket_separate_keys(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/ping")).status_code == 200
        assert (await client.get("/hello")).status_code == 200
        assert (await client.get("/ping")).status_code == 200  # Should be 200!
        r4 = await client.get("/ping")
        assert r4.status_code == 429  # Now this should be 429


@pytest.mark.asyncio
async def test_token_bucket_multiple_limiters():
    app = FastAPI()
    limiter1 = TokenBucketRateLimiter(capacity=1, tokens_per_second=1, prefix="short")
    limiter2 = TokenBucketRateLimiter(capacity=2, tokens_per_second=2, prefix="long")

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
        # Wait for limiter1 window to refill
        await asyncio.sleep(1.1)
        # Third request: limiter1 allows, limiter2 allows (counter=2)
        r3 = await client.get("/multi")
        assert r3.status_code == 200
        # Fourth request: limiter1 allows, limiter2 blocks (counter=3, limit=2)
        r4 = await client.get("/multi")
        assert r4.status_code == 429
