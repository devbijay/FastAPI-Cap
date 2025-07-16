# Advanced Usage with Dependency Injection

This guide explores the advanced features of `fastapicap`, primarily focusing on its integration with FastAPI's dependency injection system for fine-grained rate limiting control. All examples assume that `Cap.init_app` has been called once during your application's startup (e.g., using FastAPI's `lifespan` event) to initialize the Redis connection.

## Core Concept: Limiters as Dependencies

While `fastapicap` provides a `RateLimitMiddleware` for applying global rate limits, the most powerful and flexible approach is to use limiters as dependencies. This allows you to apply different rate-limiting rules to each endpoint with fine-grained control.

All limiter strategies in `fastapicap` are designed to be used directly with FastAPI's `Depends()` system.

Every limiter, such as `RateLimiter` (for Fixed Window) or `TokenBucketRateLimiter`, can be instantiated and then injected directly into your path operation functions.

This pattern is powerful because it allows you to:
- Apply different limits to different endpoints (e.g., 10 requests/minute for `/free_tier` vs. 1000 requests/minute for `/paid_tier`).
- Use different strategies for different endpoints.
- Customize the rate limit key and response on a per-limiter basis.

### Example: Per-Endpoint Rate Limiting

Here’s how you can apply different limits to two separate endpoints.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapicap import Cap, RateLimiter, TokenBucketRateLimiter

# Define a lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Cap with your Redis URL
    # This manages the connection for all limiters
    Cap.init_app(redis_url="redis://localhost:6379/0")
    yield


app = FastAPI(lifespan=lifespan)

# Create two different limiter instances
login_limiter = TokenBucketRateLimiter(capacity=3, tokens_per_minute=1) # 3 attempts per minute
profile_limiter = RateLimiter(limit=100, seconds=60) # 100 requests per minute

@app.post("/login")
async def login(_=Depends(login_limiter)):
    return {"message": "Login successful"}

@app.get("/users/me")
async def get_user_profile(_=Depends(profile_limiter)):
    return {"user": "details"}
```

## Custom Key Function (`key_func`)

You can easily change how a client is identified for a specific limiter by passing a `key_func`. For example, you might want to rate-limit based on an API key provided in the headers instead of the client's IP address, and also ensure that the limit is applied per route.

```python
from fastapi import FastAPI, Depends, Request
from fastapicap import SlidingWindowLogRateLimiter

app = FastAPI()

# Define a key function that uses an 'X-API-Key' header AND the request path
async def get_key_from_api_key(request: Request) -> str:
    api_key = request.headers.get("X-API-Key", "anonymous")
    # Include the request path to make the key unique per API key AND per route
    return f"{api_key}:{request.url.path}"

# Create a limiter that uses our custom key function
api_key_limiter = SlidingWindowLogRateLimiter(
    limit=100,
    window_seconds=60,
    key_func=get_key_from_api_key
)

@app.get("/data")
async def get_data(_=Depends(api_key_limiter)):
    return {"data": "some secret data"}
```

### Common `key_func` Examples

Here are some common `key_func` patterns you can use, depending on your rate-limiting requirements. Remember to use `Request` from `fastapi`.

```python
from fastapi import Request
from fastapicap.base_limiter import get_client_ip # Helper to get client IP

# 1. Rate limiting based on User ID (e.g., from a JWT or session)
# Assumes you have a way to extract user_id from the request (e.g., via a dependency)
async def key_by_user_id(request: Request) -> str:
    # Replace with your actual user ID extraction logic
    # For example, if using FastAPI's security dependencies:
    # current_user = await get_current_user(request)
    # user_id = current_user.id
    user_id = request.headers.get("X-User-ID", "anonymous_user")
    return f"user:{user_id}"

# 2. Rate limiting based on User ID AND Request Path
# This ensures a user has a separate limit for each endpoint they access.
async def key_by_user_id_and_path(request: Request) -> str:
    user_id = request.headers.get("X-User-ID", "anonymous_user")
    return f"user:{user_id}:path:{request.url.path}"

# 3. Rate limiting based on User ID AND Client IP
# Useful for preventing a single user from abusing multiple IPs, or multiple users from a single IP.
async def key_by_user_id_and_ip(request: Request) -> str:
    user_id = request.headers.get("X-User-ID", "anonymous_user")
    client_ip = get_client_ip(request)
    return f"user:{user_id}:ip:{client_ip}"

# 4. Rate limiting based on User ID AND Client IP AND Request Path
# The most granular level, ensuring a unique limit for each user from each IP to each specific path.
async def key_by_user_id_ip_and_path(request: Request) -> str:
    user_id = request.headers.get("X-User-ID", "anonymous_user")
    client_ip = get_client_ip(request)
    return f"user:{user_id}:ip:{client_ip}:path:{request.url.path}"

# 5. Rate limiting based on a specific Path Parameter (e.g., user_id in /users/{user_id})
# This requires accessing path parameters, which are typically available after routing.
# You might need to adjust how you pass the request to the key_func if using it directly
# in Depends() and relying on path params that aren't yet resolved.
# A more robust way for path params is to define a dependency that extracts it.
async def key_by_path_parameter(request: Request) -> str:
    # This is a simplified example. In a real scenario, you'd get the path param
    # from request.path_params or a custom dependency that extracts it.
    # For example, if your route is /items/{item_id}
    item_id = request.path_params.get("item_id", "no_item_id")
    return f"item:{item_id}"

# Example of using a custom key_func with a limiter:
# from fastapicap import RateLimiter
# my_limiter = RateLimiter(limit=10, seconds=60, key_func=key_by_user_id_and_path)
# @app.get("/protected", dependencies=[Depends(my_limiter)])
# async def protected_route():
#     return {"message": "Protected data"}
```

## Custom On-Limit Handler (`on_limit`)

You can also customize the response when a rate limit is exceeded for a specific endpoint. The `on_limit` handler is a function that gets called when the limit is hit. By default, it raises a `429 HTTPException`.

Your custom handler receives the `request`, `response`, and `retry_after` value.

```python
from fastapi import FastAPI, Depends, Request, Response, HTTPException
from fastapicap import RateLimiter

app = FastAPI()

# Define a custom handler
def custom_limit_handler(request: Request, response: Response, retry_after: int):
    raise HTTPException(
        status_code=429,
        detail=f"Custom limit exceeded for path {request.url.path}.",
        headers={"Retry-After": str(retry_after)},
    )

# Create a limiter with the custom handler
custom_limiter = RateLimiter(
    limit=5,
    seconds=10,
    on_limit=custom_limit_handler
)

@app.get("/special")
async def special_endpoint(_=Depends(custom_limiter)):
    return {"message": "A special response"}
```

## Global Limiting with Middleware (Optional)

While dependency injection is preferred for most cases, you can use `RateLimitMiddleware` to apply a global, baseline limit. You can even combine both approaches: use the middleware for a general limit and apply stricter, more specific limits on certain endpoints using `Depends()`.

The middleware is also where you can configure a `metrics_callback` for monitoring systems like Prometheus.

```python
from fastapi import FastAPI, Request
from fastapicap import RateLimitMiddleware, RateLimitConfig, RateLimiter

app = FastAPI()

# Example callback for metrics
async def metrics_callback(request: Request, limited: bool):
    if limited:
        print(f"Request to {request.url.path} was rate-limited.")

config = RateLimitConfig(metrics_callback=metrics_callback)
limiter = RateLimiter(limit=1000, seconds=60) # Global limit

app.add_middleware(
    RateLimitMiddleware,
    limiters=[limiter],
    config=config
)
```