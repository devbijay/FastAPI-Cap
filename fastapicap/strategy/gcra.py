import time
from typing import Optional, Callable
from fastapi import Request, Response

from ..base_limiter import BaseLimiter
from ..lua import GCRA_LUA


class GCRARateLimiter(BaseLimiter):
    """
    Implements the Generic Cell Rate Algorithm (GCRA) for rate limiting.

    GCRA is a popular algorithm that controls the rate of events by tracking
    the "Theoretical Arrival Time" (TAT) of the next allowed event. It's often
    used for API rate limiting as it provides a smooth, burstable rate.

    This limiter allows for a burst of requests up to `burst` capacity,
    and then enforces a steady rate defined by `tokens_per_second`,
    `tokens_per_minute`, `tokens_per_hour`, or `tokens_per_day`.

    Args:
        burst (int): The maximum number of additional requests that can be
            served instantly (i.e., the "burst" capacity beyond the steady rate).
            This defines how many requests can be handled without delay if
            the system has been idle.
        tokens_per_second (float): The steady rate of tokens allowed per second.
            If combined with other `tokens_per_*` arguments, they are summed.
            Defaults to 0.
        tokens_per_minute (float): The steady rate of tokens allowed per minute.
            Defaults to 0.
        tokens_per_hour (float): The steady rate of tokens allowed per hour.
            Defaults to 0.
        tokens_per_day (float): The steady rate of tokens allowed per day.
            Defaults to 0.
        key_func (Optional[Callable[[Request], str]]): An asynchronous function
            to extract a unique key from the request. This key is used to
            identify the subject being rate-limited (e.g., client IP, user ID).
            If `None`, `BaseLimiter._default_key_func` (client IP + path) is used.
        on_limit (Optional[Callable[[Request, Response, int], None]]): An
            asynchronous function called when the rate limit is exceeded.
            It receives the `request`, `response` object, and the `retry_after`
            value in seconds. If `None`, `BaseLimiter._default_on_limit`
            (which raises an `HTTPException 429`) is used.
        prefix (str): A string prefix for all Redis keys used by this limiter.
            Defaults to "cap".

    Attributes:
        burst (int): The configured burst capacity.
        tokens_per_second (float): The total calculated steady rate in tokens per second.
        period (float): The calculated time period (in milliseconds) between allowed tokens.
        lua_script (str): The Lua script used for GCRA logic in Redis.
        _instance_id (str): A unique identifier for this limiter instance, used
            to create distinct Redis keys.

    Raises:
        ValueError: If the total calculated `tokens_per_second` is not positive.
            This ensures that a meaningful rate limit is defined.

    Note:
        The `GCRA_LUA` script handles the core rate-limiting logic in Redis,
        ensuring atomic operations. The `retry_after` value returned by the
        Lua script (if a limit is hit) indicates the number of milliseconds
        until the next request would be allowed.
    """

    def __init__(
        self,
        burst: int,
        tokens_per_second: float = 0,
        tokens_per_minute: float = 0,
        tokens_per_hour: float = 0,
        tokens_per_day: float = 0,
        key_func: Optional[Callable[[Request], str]] = None,
        on_limit: Optional[Callable[[Request, Response, int], None]] = None,
        prefix: str = "cap",
    ):
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        self.burst = burst
        total_tokens_per_second = (
            tokens_per_second
            + tokens_per_minute / 60
            + tokens_per_hour / 3600
            + tokens_per_day / 86400
        )
        if total_tokens_per_second <= 0:
            raise ValueError(
                "At least one of tokens_per_second, tokens_per_minute, "
                "tokens_per_hour, or tokens_per_day must be positive."
            )

        self.tokens_per_second = total_tokens_per_second
        self.period = 1000.0 / self.tokens_per_second
        self.lua_script = GCRA_LUA
        self._instance_id = f"gcra_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        """
        Executes the GCRA rate-limiting logic for the incoming request.

        This method is designed to be used as a FastAPI dependency or decorator.
        It interacts with Redis to check if the request is allowed based on
        the configured GCRA parameters. If the limit is exceeded, it calls
        the `on_limit` handler.

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
            str(self.burst),
            str(self.tokens_per_second / 1000),  # tokens/ms
            str(self.period),
            str(now),
        )
        allowed = result[0] == 1
        retry_after = int(result[1]) if not allowed else 0
        if not allowed:
            await self._safe_call(self.on_limit, request, response, retry_after)
