import time
from typing import Optional, Callable
from fastapi import Request, Response

from ..connection import Cap
from ..base_limiter import BaseLimiter
from ..lua import GCRA_LUA


class GCRARateLimiter(BaseLimiter):
    def __init__(
        self,
        burst: int,
        tokens_per_second: float = 0,
        tokens_per_minute: float = 0,
        tokens_per_hour: float = 0,
        tokens_per_day: float = 0,
        key_func: Optional[Callable] = None,
        on_limit: Optional[Callable] = None,
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
        await self._ensure_lua_sha(self.lua_script)
        key = await self.key_func(request)
        redis = Cap.redis
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
            await self.on_limit(request, response, retry_after)
