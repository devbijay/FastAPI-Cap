from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis


class Cap:
    """
    Singleton-style Redis connection manager for Cap.

    This class provides a shared, async Redis connection for all rate limiter
    instances. It is not meant to be instantiated; use the classmethod
    `init_app` to initialize the connection.

    Attributes:
        redis: The shared aioredis Redis connection instance.

    Example:
        Cap.init_app("redis://localhost:6379/0")
        # Now Cap.redis can be used by all limiters.
    """

    redis: Optional[Redis] = None

    def __init__(self) -> None:
        """
        Prevent instantiation of Cap.

        Raises:
            RuntimeError: Always, to enforce singleton usage.
        """
        raise RuntimeError("Use classmethods only; do not instantiate Cap.")

    @classmethod
    def init_app(cls, redis_url: str) -> None:
        """
        Initialize the shared Redis connection for Cap.

        Args:
            redis_url (str): The Redis connection URL.

        Example:
            Cap.init_app("redis://localhost:6379/0")
        """
        cls.redis = aioredis.from_url(redis_url, decode_responses=True)
