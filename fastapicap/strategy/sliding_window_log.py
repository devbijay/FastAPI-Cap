import time
from typing import Optional, Callable
from fastapi import Request, Response

from ..base_limiter import BaseLimiter
from ..lua import SLIDING_LOG_LUA


class SlidingWindowLogRateLimiter(BaseLimiter):
    """
    Implements a **Sliding Window (Log-based)** rate limiting algorithm.

    This is the most accurate form of the sliding window algorithm. It works by
    storing a timestamp for every request made by a client within a Redis sorted set.
    When a new request comes in, the algorithm first removes all timestamps that
    fall outside the current sliding window. Then, it counts the number of remaining
    timestamps within the window. If this count is below the `limit`, the request
    is allowed, and its timestamp is added to the set. This method ensures
    precise rate limiting as the window truly "slides" over time.

    Args:
        limit (int): The maximum number of requests allowed within the defined
            sliding window. Must be a positive integer.
        window_seconds (int): The number of seconds defining the size of the
            sliding window. Can be combined with minutes, hours, or days.
            Defaults to 0.
        window_minutes (int): The number of minutes defining the window size.
            Defaults to 0.
        window_hours (int): The number of hours defining the window size.
            Defaults to 0.
        window_days (int): The number of days defining the window size.
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
        limit (int): The maximum requests allowed within the sliding window.
        window_seconds (int): The total calculated window size in seconds.
        lua_script (str): The Lua script used for the log-based sliding window
            logic in Redis.
        _instance_id (str): A unique identifier for this limiter instance, used
            to create distinct Redis keys for isolation.

    Raises:
        ValueError: If the `limit` is not positive or if the calculated
            `window_seconds` is not positive (i.e., all time units are zero).

    Note:
        This implementation uses Redis sorted sets (`ZADD`, `ZREMRANGEBYSCORE`, `ZCARD`)
        to store and manage request timestamps, ensuring atomic operations
        for accurate rate limiting.
    """
    def __init__(
        self,
        limit: int,
        window_seconds: int = 0,
        window_minutes: int = 0,
        window_hours: int = 0,
        window_days: int = 0,
        key_func: Optional[Callable[[Request], str]] = None,
        on_limit: Optional[Callable[[Request, Response, int], None]] = None,
        prefix: str = "cap",
    ):
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        self.limit = limit
        if limit <= 0:
            raise ValueError("Limit must be a positive integer.")
        self.window_seconds = (
            window_seconds
            + window_minutes * 60
            + window_hours * 3600
            + window_days * 86400
        )
        if self.window_seconds <= 0:
            raise ValueError(
                "Window must be positive (set seconds, minutes, hours, or days)"
            )
        self.lua_script = SLIDING_LOG_LUA
        self._instance_id = f"sliding_log_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        """
        Applies the log-based sliding window rate limiting logic to the incoming request.

        This method is the core of the rate limiter. It interacts with Redis to
        manage request timestamps within a sorted set and checks if the total
        count within the current sliding window exceeds the configured limit.

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
        window_ms = self.window_seconds * 1000
        result = await redis.evalsha(
            self.lua_sha,
            1,
            full_key,
            str(now),
            str(window_ms),
            str(self.limit),
        )
        allowed = result == 1
        retry_after = 0 if allowed else int(result)
        if not allowed:
            await self._safe_call(self.on_limit, request, response, retry_after)
