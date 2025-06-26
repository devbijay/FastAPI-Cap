# FastAPI Cap Quick Start

**FastAPI Cap** is a robust, extensible rate limiting library for FastAPI, powered by Redis. This guide will help you get started quickly with the Fixed Window rate limiting strategy.

---

## 1. Installation

Install the package using pip:

```bash
pip install fastapicap
```

**Note**: You also need a running Redis instance. You can run one locally using Docker:


---

## 2. Initialize the App

Before using any limiter, you must initialize the shared Redis connection.  
You can do this in your FastAPI app's lifespan event or directly at startup.

```python
from fastapi import FastAPI
from fastapicap import Cap

app = FastAPI()
Cap.init_app("redis://localhost:6379/0")

```

---

## 3. Using the Fixed Window Rate Limiter

Import the `RateLimiter` (Also Known As Fixed Window Rate Limiter) and use it as a dependency on your route:

```python
from fastapi import Depends
limiter1 = RateLimiter(limit=5, minutes=1)

@app.get("/limited", dependencies=[Depends(limiter1)])
async def limited_endpoint():
    return {"message": "You are within the rate limit!"}
```

If the limit is exceeded, the client receives a `429 Too Many Requests` response with a `Retry-After` header.

---

## 4. Using Multiple Limiters on a Single Route

You can combine multiple limiters for more granular control.  
For example, to allow **1 request per second** and **30 requests per minute**:

```python
from fastapi import FastAPI, Depends
from fastapicap import Cap, RateLimiter

## App Init part

limiter_1s = RateLimiter(limit=1, seconds=1)
limiter_30m = RateLimiter(limit=30, minutes=1)

@app.get("/strict", dependencies=[Depends(limiter_1s), Depends(limiter_30m)])
async def strict_endpoint():
    return {"message": "You passed both rate limits!"}
```

If either limit is exceeded, the request will be blocked.

---

### **Notes**

- The default key for rate limiting is based on the client IP and request path.
- All limiters are backed by Redis and require a working Redis connection.
- Only dependency-based usage is currently supported and tested.

---

## 5. Customizing `on_limit` and `key_func` in FastAPI Cap
FastAPI Cap allows you to customize how rate limits are enforced and how unique clients are identified by providing your own `on_limit` and `key_func` functions to any limiter.
This guide explains how to use and implement custom `on_limit` and `key_func` functions, including the parameters they receive.


### Default `key_func` Implementation

By default, FastAPI Cap uses the client IP address and request path to generate a unique key for each client and endpoint.

```python
@staticmethod
async def _default_key_func(request: Request) -> str:
    """
    Default key function: uses client IP and request path.
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{request.url.path}"
```
- **Parameters:**  
  - `request`: The FastAPI `Request` object.
- **Returns:**  
  - A string key in the format `client_ip:/path`.

### Default `on_limit` Implementation

By default, FastAPI Cap raises a `429 Too Many Requests` HTTPException and sets the `Retry-After` header.

```python
@staticmethod
async def _default_on_limit(request, response, retry_after: int) -> None:
    """
    Default handler when the rate limit is exceeded.
    """
    from fastapi import HTTPException

    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded. Please try again later.",
        headers={"Retry-After": str(retry_after)},
    )
```

- **Parameters:**  
  - `request`: The FastAPI `Request` object.
  - `response`: The FastAPI `Response` object (not used in the default).
  - `retry_after`: An integer indicating how many seconds to wait before retrying.

---


### Custom `key_func`

The `key_func` is responsible for generating a unique key for each client/request.  
You can provide your own logic to rate limit by user ID, API key, or any other identifier.

### **Signature**

```python
async def key_func(request: Request) -> str:
    ...
```

### **Example: Rate Limit by User ID**

```python
from fastapi import Request

async def user_id_key_func(request: Request) -> str:
    # Assume user ID is stored in request.state.user_id
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        # Fallback to IP if user is not authenticated
        client_ip = request.client.host if request.client else "unknown"
        return f"anon:{client_ip}:{request.url.path}"
    return f"user:{user_id}:{request.url.path}"
```

**Usage:**

```python
limiter = RateLimiter(limit=10, minutes=1, key_func=user_id_key_func)
```

### **Using Your Custom `on_limit`  Handler**

The `on_limit` function is called when a client exceeds the rate limit.  
You can customize this to log, return a custom response, or perform other actions.

### Signature

```python
async def on_limit(request: Request, response: Response, retry_after: int) -> None:
    ...
```

### **Example: Custom JSON Error Response**

```python
from fastapi import Request, Response
from fastapi.responses import JSONResponse

async def custom_on_limit(request: Request, response: Response, retry_after: int):
    response = JSONResponse(
        status_code=429,
        content={
            "error": "Too many requests",
            "retry_after": retry_after,
            "detail": "Please slow down!"
        },
        headers={"Retry-After": str(retry_after)},
    )
    raise response
```

**Usage:**

```python
limiter = RateLimiter(limit=5, minutes=1, on_limit=custom_on_limit)
```

---


## Next Steps

- Explore other strategies: Sliding Window, Token Bucket, Leaky Bucket, GCRA, and Sliding Window Log.

---

**Happy rate limiting!**