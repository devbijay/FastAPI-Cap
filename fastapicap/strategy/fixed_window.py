from typing import Optional, Callable
from fastapi import Request, Response

from ..connection import Cap
from ..base_limiter import BaseLimiter
from ..lua import FIXED_WINDOW


class RateLimiter(BaseLimiter):
    """
    Initialize the fixed window rate limiter.

    Args:
        limit (int): Maximum number of requests allowed per window.
        seconds (int): Number of seconds in the window.
        minutes (int): Number of minutes in the window.
        hours (int): Number of hours in the window.
        days (int): Number of days in the window.
        key_func (Optional[Callable]): Async function to extract a unique key from the request.
            Defaults to client IP and path.
        on_limit (Optional[Callable]): Async function called when the rate limit is exceeded.
            Defaults to raising HTTP 429.
        prefix (str): Redis key prefix for all limiter keys.

    Raises:
        ValueError: If the window size is not positive (i.e., all of seconds, minutes, hours, and days are zero).
            This ensures that the rate limiter is always configured with a valid, non-zero window.
    """

    def __init__(
        self,
        limit: int,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        key_func: Optional[Callable] = None,
        on_limit: Optional[Callable] = None,
        prefix: str = "cap",
    ):
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        self.limit = limit
        self.window_ms = (
            (seconds * 1000)
            + (minutes * 60 * 1000)
            + (hours * 60 * 60 * 1000)
            + (days * 24 * 60 * 60 * 1000)
        )
        self.lua_script = FIXED_WINDOW
        self._instance_id = f"limiter_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        """
        Apply the rate limiting logic to the incoming request.

        Args:
            request (Request): The incoming FastAPI request.
            response (Response): The FastAPI response object.

        Raises:
            HTTPException: If the rate limit is exceeded (via on_limit handler).
        """
        await self._ensure_lua_sha(self.lua_script)
        key = await self.key_func(request)
        full_key = f"{self.prefix}:{self._instance_id}:{key}"
        redis = Cap.redis
        result = await redis.evalsha(
            self.lua_sha, 1, full_key, str(self.limit), str(self.window_ms)
        )
        allowed = result == 0
        retry_after = int(result / 1000) if not allowed else 0
        if not allowed:
            await self.on_limit(request, response, retry_after)
