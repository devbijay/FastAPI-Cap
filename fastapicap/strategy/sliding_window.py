import time
from typing import Optional, Callable
from fastapi import Request, Response
from ..base_limiter import BaseLimiter
from ..lua import SLIDING_WINDOW


class SlidingWindowRateLimiter(BaseLimiter):
    """
    Implements an **Approximated Sliding Window** rate limiting algorithm.

    This algorithm provides a more accurate and smoother rate limiting experience
    than a simple Fixed Window, while being more memory-efficient than a pure
    log-based sliding window. It works by maintaining counters for the current
    fixed window and the immediately preceding fixed window. The effective count
    for the sliding window is then calculated as a weighted sum of the requests
    in the previous window and the current window, based on how much of the
    previous window still "slides" into the current view.

    Args:
        limit (int): The maximum number of requests allowed within the defined
            sliding window. Must be a positive integer.
        seconds (int): The number of seconds defining the size of the
            *individual fixed window segments* that make up the sliding window.
            This value, combined with others, determines the `window_ms`.
            Defaults to 0.
        minutes (int): The number of minutes defining the window segment size.
            Defaults to 0.
        hours (int): The number of hours defining the window segment size.
            Defaults to 0.
        days (int): The number of days defining the window segment size.
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
        window_ms (int): The calculated size of a single fixed window segment
            in milliseconds (e.g., if you set `seconds=60`, this is 60000ms).
            The sliding window itself covers a period equivalent to `window_ms`.
        lua_script (str): The Lua script used for the approximated sliding
            window logic in Redis.
        _instance_id (str): A unique identifier for this limiter instance, used
            to create distinct Redis keys for isolation.

    Raises:
        ValueError: If the `limit` is not positive or if the calculated
            `window_ms` is not positive (i.e., all time units are zero).

    Note:
        This implementation relies on a Redis Lua script to atomically manage
        and count requests within the current and previous fixed window segments.
        The `retry_after` value provided by the Lua script indicates the
        approximate time in seconds until the next request might be allowed.
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
    ):
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        self.limit = limit
        if limit <= 0:
            raise ValueError("Limit must be a positive integer.")
        self.window_ms = (
            (seconds * 1000)
            + (minutes * 60 * 1000)
            + (hours * 60 * 60 * 1000)
            + (days * 24 * 60 * 60 * 1000)
        )
        self.lua_script = SLIDING_WINDOW
        self._instance_id = f"sliding_window_limiter_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        """
        Applies the approximated sliding window rate limiting logic to the incoming request.

        This method is the core of the rate limiter. It interacts with Redis to
        increment counters for the current and previous window segments and
        checks if the estimated count within the sliding window exceeds the limit.

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
        now_ms = int(time.time() * 1000)
        curr_window_start = now_ms - (now_ms % self.window_ms)
        prev_window_start = curr_window_start - self.window_ms
        curr_key = f"{self.prefix}:{self._instance_id}:{key}:{curr_window_start}"
        prev_key = f"{self.prefix}:{self._instance_id}:{key}:{prev_window_start}"
        result = await redis.evalsha(
            self.lua_sha,
            2,
            curr_key,
            prev_key,
            str(curr_window_start),
            str(self.window_ms),
            str(self.limit),
        )
        allowed = result == 0
        retry_after = int(result / 1000) if not allowed else 0
        if not allowed:
            await self._safe_call(self.on_limit, request, response, retry_after)
