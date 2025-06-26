from typing import Optional, Callable
from fastapi import Request, Response

from ..base_limiter import BaseLimiter
from ..lua import FIXED_WINDOW


class RateLimiter(BaseLimiter):
    """
    Implements a Fixed Window rate limiting algorithm.

    This limiter restricts the number of requests within a fixed time window.
    When a new window starts, the counter resets to zero. All requests within
    the same window consume from the same counter.

    Args:
        limit (int): The maximum number of requests allowed within the defined window.
            Must be a positive integer.
        seconds (int): The number of seconds defining the window size.
            Can be combined with minutes, hours, or days. Defaults to 0.
        minutes (int): The number of minutes defining the window size.
            Defaults to 0.
        hours (int): The number of hours defining the window size.
            Defaults to 0.
        days (int): The number of days defining the window size.
            Defaults to 0.
        key_func (Optional[Callable[[Request], str]]): An asynchronous or
            synchronous function to extract a unique key from the request.
            Defaults to client IP and path.
        on_limit (Optional[Callable[[Request, Response, int], None]]): An
            asynchronous or synchronous function called when the rate limit is exceeded.
            Defaults to raising HTTP 429.
        prefix (str): Redis key prefix for all limiter keys.
            Defaults to "cap".

    Attributes:
        limit (int): The maximum requests allowed per window.
        window_ms (int): The calculated window size in milliseconds.
        lua_script (str): The Lua script used for fixed window logic in Redis.
        _instance_id (str): A unique identifier for this limiter instance, used
            to create distinct Redis keys.

    Raises:
        ValueError: If the `limit` is not positive or if the calculated
            `window_ms` is not positive (i.e., all time units are zero).
    """

    def __init__(
        self,
        limit: int,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        key_func: Optional[Callable[[Request], str]] = None,
        on_limit: Optional[Callable[[Request, Response, int], None]] = None,
        prefix: str = "cap",
    )-> None:
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        self.limit = limit
        self.window_ms = (
            (seconds * 1000)
            + (minutes * 60 * 1000)
            + (hours * 60 * 60 * 1000)
            + (days * 24 * 60 * 60 * 1000)
        )
        self.lua_script = FIXED_WINDOW
        self._instance_id: str = f"fixed_window_limiter_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        """
        Apply the rate limiting logic to the incoming request. It interacts with Redis to
        increment a counter within the current time window and checks if the
        limit has been exceeded.

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
        result = await redis.evalsha(
            self.lua_sha, 1, full_key, str(self.limit), str(self.window_ms)
        )
        allowed = result == 0
        retry_after = int(result / 1000) if not allowed else 0
        if not allowed:
            await self._safe_call(self.on_limit, request, response, retry_after)
