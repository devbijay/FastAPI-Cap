import time
from typing import Optional, Callable
from fastapi import Request, Response

from ..connection import Cap
from ..base_limiter import BaseLimiter
from ..lua import SLIDING_LOG_LUA


class SlidingWindowLogRateLimiter(BaseLimiter):
    def __init__(
        self,
        limit: int,
        window_seconds: int = 0,
        window_minutes: int = 0,
        window_hours: int = 0,
        window_days: int = 0,
        key_func: Optional[Callable] = None,
        on_limit: Optional[Callable] = None,
        prefix: str = "cap",
    ):
        super().__init__(key_func=key_func, on_limit=on_limit, prefix=prefix)
        self.limit = limit
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
        self._instance_id = f"slidinglog_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        await self._ensure_lua_sha(self.lua_script)
        key = await self.key_func(request)
        redis = Cap.redis
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
            await self.on_limit(request, response, retry_after)
