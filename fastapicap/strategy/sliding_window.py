import time
from typing import Optional, Callable
from fastapi import Request, Response
from ..connection import Cap
from ..base_limiter import BaseLimiter
from ..lua import SLIDING_WINDOW


class SlidingWindowRateLimiter(BaseLimiter):
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
        self.window_ms = (
            (seconds * 1000)
            + (minutes * 60 * 1000)
            + (hours * 60 * 60 * 1000)
            + (days * 24 * 60 * 60 * 1000)
        )
        self.lua_script = SLIDING_WINDOW
        self._instance_id = f"limiter_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        await self._ensure_lua_sha(self.lua_script)
        key: str = await self._safe_call(self.key_func, request)
        redis = Cap.redis
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
