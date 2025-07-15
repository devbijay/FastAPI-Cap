import asyncio
import logging
from typing import Callable, List, Optional
from fastapi import Response
from fastapi.responses import JSONResponse
from dataclasses import dataclass
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from fastapicap.base_limiter import BaseLimiter

logger = logging.getLogger("rate_limit")


@dataclass
class RateLimitConfig:
    enabled: bool = True
    fail_open: bool = False  # Allow requests if Redis is down
    shadow_mode: bool = False  # Log limits but don't enforce
    metrics_callback: Optional[Callable] = None  # For monitoring


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        limiters: List[BaseLimiter],
        *,
        config: Optional[RateLimitConfig] = None,
        on_limit: Optional[Callable] = None,
        exclude_paths: Optional[List[str]] = None,
        exclude_methods: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.limiters = limiters
        self.config = config or RateLimitConfig()
        self.on_limit = on_limit or self._default_on_limit
        self.exclude_paths = set(exclude_paths or [])
        self.exclude_methods = set(exclude_methods or ["OPTIONS", "HEAD"])

    async def dispatch(
        self, request: StarletteRequest, call_next: Callable
    ) -> StarletteResponse:
        if (
            not self.config.enabled
            or request.method in self.exclude_methods
            or any(request.url.path.startswith(path) for path in self.exclude_paths)
        ):
            return await call_next(request)

        if self.config.shadow_mode:
            await self._log_shadow_limits(request)
            return await call_next(request)

        try:
            dummy_response = StarletteResponse()
            await asyncio.gather(
                *(limiter(request, dummy_response) for limiter in self.limiters)
            )
            return await call_next(request)
        except Exception as e:
            return await self._handle_rate_limit_exception(request, e, call_next)

    async def _default_on_limit(
        self, request: StarletteRequest, retry_after: int
    ) -> Response:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )

    async def _log_shadow_limits(self, request: StarletteRequest) -> None:
        dummy_response = StarletteResponse()
        for limiter in self.limiters:
            try:
                await limiter(request, dummy_response)
            except Exception as e:
                if getattr(e, "status_code", None) == 429:
                    logger.info(
                        f"Shadow limit exceeded for {limiter.__class__.__name__}: {getattr(e, 'detail', 'No detail')}"
                    )
                else:
                    logger.error(
                        f"Limiter {limiter.__class__.__name__} failed in shadow mode: {e}",
                        exc_info=True,
                    )

    async def _handle_rate_limit_exception(
        self, request: StarletteRequest, exc: Exception, call_next: Callable
    ) -> StarletteResponse:
        if getattr(exc, "status_code", None) == 429:
            if self.config.metrics_callback:
                await self.config.metrics_callback(request, False)
            return await self.on_limit(
                request, int(exc.headers.get("Retry-After", "1"))
            )

        if self.config.fail_open:
            logger.error(f"Rate limit failed, failing open: {str(exc)}")
            return await call_next(request)

        raise exc
