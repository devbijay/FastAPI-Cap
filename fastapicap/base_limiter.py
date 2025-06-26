from typing import Optional, Callable, TYPE_CHECKING
from .connection import Cap



class BaseLimiter:
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
        self.key_func = key_func or self._default_key_func
        self.on_limit = on_limit or self._default_on_limit
        self.prefix = prefix
        self.lua_sha = None

    async def _ensure_lua_sha(self, lua_script: str)-> None:
        """
        Ensure the Lua script is loaded into Redis and store its SHA1 hash.

        Args:
            lua_script (str): The Lua script to load.
        """
        if self.lua_sha is None:
            redis = Cap.redis
            self.lua_sha = await redis.script_load(lua_script)

    @staticmethod
    async def _default_key_func(request):
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
            client_ip = request.client.host
        return f"{client_ip}:{request.url.path}"

    @staticmethod
    async def _default_on_limit(request, response, retry_after: int):
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
