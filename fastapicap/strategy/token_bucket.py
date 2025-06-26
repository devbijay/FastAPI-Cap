import time
from typing import Optional, Callable
from fastapi import Request, Response

from ..base_limiter import BaseLimiter
from ..lua import TOKEN_BUCKET


class TokenBucketRateLimiter(BaseLimiter):
    """
    Implements the Token Bucket rate limiting algorithm.

    The Token Bucket algorithm works like a bucket that tokens are continuously
    added to at a fixed `refill_rate`. Each request consumes one token.
    If a request arrives and there are tokens available in the bucket,
    the request is processed, and a token is removed. If the bucket is empty,
    the request is denied (or queued). The `capacity` defines the maximum
    number of tokens the bucket can hold, allowing for bursts of traffic
    up to that capacity. This algorithm is excellent for controlling the
    average rate of requests while permitting bursts.

    Args:
        capacity (int): The maximum number of tokens the bucket can hold.
            This determines the maximum burst size allowed. Must be a
            positive integer.
        tokens_per_second (float): The rate at which tokens are added to the
            bucket, in tokens per second. If combined with other `tokens_per_*`
            arguments, they are summed to determine the total `refill_rate`.
            Defaults to 0.
        tokens_per_minute (float): The token refill rate in tokens per minute.
            Defaults to 0.
        tokens_per_hour (float): The token refill rate in tokens per hour.
            Defaults to 0.
        tokens_per_day (float): The token refill rate in tokens per day.
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
        refill_rate (float): The total calculated token refill rate in
            tokens per millisecond.
        lua_script (str): The Lua script used for token bucket logic in Redis.
        _instance_id (str): A unique identifier for this limiter instance, used
            to create distinct Redis keys for isolation.

    Raises:
        ValueError: If the `capacity` is not positive, or if the total
            calculated `refill_rate` is not positive. This ensures a valid
            configuration for the token bucket.
    """
    def __init__(
        self,
        capacity: int,
        tokens_per_second: float = 0,
        tokens_per_minute: float = 0,
        tokens_per_hour: float = 0,
        tokens_per_day: float = 0,
        key_func: Optional[Callable[[Request], str]] = None,
        on_limit: Optional[Callable[[Request, Response, int], None]] = None,
        prefix: str = "cap",
    ):
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer.")

        self.capacity = capacity
        total_tokens = (
            tokens_per_second
            + tokens_per_minute / 60
            + tokens_per_hour / 3600
            + tokens_per_day / 86400
        )
        self.refill_rate = total_tokens / 1000
        self.lua_script = TOKEN_BUCKET
        self._instance_id = f"token_bucket_limiter_{id(self)}"

        if self.refill_rate <= 0:
            raise ValueError(
                "Refill rate must be positive."
                "Check your tokens_per_second/minute/hour/day arguments."
            )

    async def __call__(self, request: Request, response: Response):
        """
        Applies the Token Bucket rate limiting logic to the incoming request.

        This method is the core of the rate limiter. It interacts with Redis to simulate
        token consumption and bucket refill, determining if the request is allowed.

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
            str(self.refill_rate),
            str(now),
        )
        allowed = result == 0
        retry_after = int(result) // 1000 if not allowed else 0
        if not allowed:
            await self._safe_call(self.on_limit, request, response, retry_after)
