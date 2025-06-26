import asyncio
import sys

import pytest
import pytest_asyncio
from testcontainers.redis import RedisContainer

from fastapicap import Cap


@pytest.fixture(scope="session")
def redis_container():
    """Start a Redis test container for the whole test session."""
    with RedisContainer() as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        url = f"redis://{host}:{port}/0"
        yield url


@pytest_asyncio.fixture(autouse=True)
async def redis_ready(redis_container):
    await Cap.init_app(redis_container)
    yield


@pytest_asyncio.fixture(autouse=True)
async def clear_redis(redis_ready):
    redis = Cap.redis
    await redis.flushdb()
    yield


if sys.platform.startswith("win"):

    @pytest.fixture(scope="session", autouse=True)
    def set_event_loop_policy():
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
