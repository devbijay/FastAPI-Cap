import time
from typing import Optional, Callable
from fastapi import Request, Response

from ..connection import Cap
from ..base_limiter import BaseLimiter
from ..lua import LEAKY_BUCKET


class LeakyBucketRateLimiter(BaseLimiter):
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
        total_leaks = (
            leaks_per_second
            + leaks_per_minute / 60
            + leaks_per_hour / 3600
            + leaks_per_day / 86400
        )
        self.leak_rate = total_leaks / 1000
        self.lua_script = LEAKY_BUCKET
        self._instance_id = f"limiter_{id(self)}"

    async def __call__(self, request: Request, response: Response):
        await self._ensure_lua_sha(self.lua_script)
        key: str = await self._safe_call(self.key_func, request)
        redis = Cap.redis
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
