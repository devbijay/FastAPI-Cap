import inspect
from abc import ABC, abstractmethod
from typing import Optional, Callable

from redis.asyncio import Redis

from .connection import Cap
from fastapi import Request, Response

class BaseLimiter(ABC):
    """
    Abstract base class for all Cap rate limiters.

    Provides common logic for key extraction, limit handling, and Lua script
    management. Subclasses should implement their own rate limiting logic
    and call `_ensure_lua_sha` to load their Lua script into Redis.

    Args:
        key_func (Optional[Callable]): Async function to extract a unique key
            from the request. Defaults to client IP and path.
        on_limit (Optional[Callable]): Async function called when the rate
            limit is exceeded. Defaults to raising HTTP 429.
        prefix (str): Redis key prefix for all limiter keys.

    Attributes:
        key_func: The function used to extract a unique key from the request.
        on_limit: The function called when the rate limit is exceeded.
        prefix: The Redis key prefix.
        lua_sha: The SHA1 hash of the loaded Lua script in Redis.

    Example:
        class MyLimiter(BaseLimiter):
            # Implement your own __call__ method
            ...
    """

    def __init__(
        self,
        key_func: Optional[Callable] = None,
        on_limit: Optional[Callable] = None,
        prefix: str = "cap",
    ) -> None:
        self.key_func: Callable[[Request], str] = key_func or self._default_key_func
        self.on_limit: Callable[[Request, Response, int], None] = (
            on_limit or self._default_on_limit
        )
        self.prefix: str = prefix
        self.lua_sha: Optional[str] = None

    async def _ensure_lua_sha(self, lua_script: str) -> None:
        """
        Ensure the Lua script is loaded into Redis and store its SHA1 hash.

        Args:
            lua_script (str): The Lua script to load.
        """
        if self.lua_sha is None:
            redis = Cap.redis
            self.lua_sha = await redis.script_load(lua_script)

    # Helper method to safely call a function, whether sync or async
    async def _safe_call(self, func: Callable, *args, **kwargs):
        """
        Safely calls a function, awaiting it if it's an asynchronous coroutine function,
        or calling it directly if it's synchronous.

        Args:
            func (Callable): The function to call.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            Any: The result of the function call.
        """
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    @staticmethod
    async def _default_key_func(request: Request) -> str:
        """
        Default key function: uses client IP and request path.

        Args:
            request: The incoming request object.

        Returns:
            str: A unique key for the client and path.
        """
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        return f"{client_ip}:{request.url.path}"

    @staticmethod
    async def _default_on_limit(request, response, retry_after: int) -> None:
        """
        Default handler when the rate limit is exceeded.

        Raises:
            HTTPException: With status 429 and a Retry-After header.
        """
        from fastapi import HTTPException

        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    @abstractmethod  # Make __call__ abstract
    async def __call__(self, request: Request, response: Response) -> None:
        """
        Abstract method that must be implemented by subclasses to define
        the specific rate limiting logic. This method makes the limiter
        callable, allowing it to be used as a FastAPI dependency or decorator.
        """
        pass

    def _ensure_redis(self) -> Redis:
        if Cap.redis is None:
            raise RuntimeError(
                "Cap.redis is not initialized. "
                "Call Cap.init_app(redis_url) before using any limiter."
            )
        return Cap.redis
