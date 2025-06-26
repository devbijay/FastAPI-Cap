import time
from typing import Optional, Callable
from fastapi import Request, Response

from ..base_limiter import BaseLimiter
from ..lua import LEAKY_BUCKET


class LeakyBucketRateLimiter(BaseLimiter):
    """
    Implements the Leaky Bucket rate limiting algorithm.

    The Leaky Bucket algorithm models traffic flow like water in a bucket.
    Requests are "drops" added to the bucket. If the bucket overflows (exceeds capacity),
    new requests are rejected. "Water" (requests) leaks out of the bucket at a
    constant rate, making space for new requests. This algorithm is known for
    producing a smooth, constant output rate of requests, which helps in
    preventing bursts from overwhelming downstream services.

    Args:
        capacity (int): The maximum capacity of the bucket. This represents
            the maximum number of requests that can be held in the bucket
            before new requests are rejected. Must be a positive integer.
        leaks_per_second (float): The rate at which requests "leak" (are processed)
            from the bucket, in requests per second. If combined with other
            `leaks_per_*` arguments, they are summed. Defaults to 0.
        leaks_per_minute (float): The leak rate in requests per minute.
            Defaults to 0.
        leaks_per_hour (float): The leak rate in requests per hour.
            Defaults to 0.
        leaks_per_day (float): The leak rate in requests per day.
            Defaults to 0.
        key_func (Optional[Callable[[Request], str]]): An asynchronous or
            synchronous function to extract a unique key from the request.
            Defaults to client IP and path. The function should accept
            a `fastapi.Request` object and return a `str`.
        on_limit (Optional[Callable[[Request, Response, int], None]]): An
            asynchronous or synchronous function called when the rate limit is exceeded.
            Defaults to raising HTTP 429. The function should accept a
            `fastapi.Request`, `fastapi.Response`, and an `int` (retry_after seconds),
            and should not return a value.
        prefix (str): Redis key prefix for all limiter keys.
            Defaults to "cap".

    Attributes:
        capacity (int): The configured maximum bucket capacity.
        leak_rate (float): The total calculated leak rate in requests per millisecond.
        lua_script (str): The Lua script used for leaky bucket logic in Redis.
        _instance_id (str): A unique identifier for this limiter instance, used
            to create distinct Redis keys for isolation.

    Raises:
        ValueError: If the `capacity` is not positive, or if the total
            calculated `leak_rate` is not positive. This ensures a valid
            configuration for the leaky bucket.
    """
    def __init__(
        self,
        capacity: int,
        leaks_per_second: float = 0,
        leaks_per_minute: float = 0,
        leaks_per_hour: float = 0,
        leaks_per_day: float = 0,
        key_func: Optional[Callable[[Request], str]] = None,
        on_limit: Optional[Callable[[Request, Response, int], None]] = None,
        prefix: str = "cap",
    ):
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        self.capacity = capacity
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer.")
        total_leaks = (
            leaks_per_second
            + leaks_per_minute / 60
            + leaks_per_hour / 3600
            + leaks_per_day / 86400
        )
        self.leak_rate = total_leaks / 1000
        self.lua_script = LEAKY_BUCKET
        self._instance_id = f"leaky_bucket_limiter_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        """
        Applies the leaky bucket rate limiting logic to the incoming request.

        This method is the core of the rate limiter. It interacts with Redis to simulate
        adding a "drop" to the bucket and checks if it overflows.

        Args:
            request (Request): The incoming FastAPI request object.
            response (Response): The FastAPI response object. This can be
                modified by the `on_limit` handler if needed.

        Raises:
            HTTPException: By default, if the rate limit is exceeded,
                `BaseLimiter._default_on_limit` will raise an `HTTPException`
                with status code 429. Custom `on_limit` functions may raise
                other exceptions or handle the response differently.
        """
        redis = self._ensure_redis()
        await self._ensure_lua_sha(self.lua_script)
        key: str = await self._safe_call(self.key_func, request)
        full_key = f"{self.prefix}:{self._instance_id}:{key}"
        now = int(time.time() * 1000)
        result = await redis.evalsha(
            self.lua_sha,
            1,
            full_key,
            str(self.capacity),
            str(self.leak_rate),
            str(now),
        )
        allowed = result == 0
        retry_after = (int(result) + 999) // 1000 if not allowed else 0
        if not allowed:
            await self._safe_call(self.on_limit, request, response, retry_after)
