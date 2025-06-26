# 🚦 FastAPI-Cap

**FastAPI-Cap** is a robust, extensible, and high-performance rate limiting library for [FastAPI](https://fastapi.tiangolo.com/) applications.  
It leverages Redis and optimized Lua scripts to provide a suite of industry-standard algorithms for controlling API traffic, preventing abuse, and ensuring reliable service delivery.

---

## ✨ Features

- **Multiple Algorithms:** Fixed Window, Sliding Window (approximated & log-based), Token Bucket, Leaky Bucket, and GCRA.
- **High Performance:** Atomic operations via Redis Lua scripts.
- **Distributed:** Consistent limits across multiple API instances.
- **Easy Integration:** Use as FastAPI dependencies or decorators.
- **Customizable:** Plug in your own key extraction and limit handling logic.
- **Battle-tested:** Designed for real-world, production-grade FastAPI services.

---

## 📦 Installation

```bash
pip install fastapicap
```

You also need a running Redis instance.  
For local development, you can use Docker:

```bash
docker run -p 6379:6379 redis
```

---

## 🚀 Quick Start

### 1. Initialize Redis Connection

```python
from fastapi import FastAPI
from fastapicap import Cap

app = FastAPI()
Cap.init_app("redis://localhost:6379/0")
```

### 2. Apply a Rate Limiter to a Route

```python
from fastapicap import RateLimiter
from fastapi import Depends

limiter = RateLimiter(limit=5, minutes=1)

@app.get("/limited", dependencies=[Depends(limiter)])
async def limited_endpoint():
    return {"message": "You are within the rate limit!"}
```

### 3. Combine Multiple Limiters

```python
limiter_1s = RateLimiter(limit=1, seconds=1)
limiter_30m = RateLimiter(limit=30, minutes=1)

@app.get("/strict", dependencies=[Depends(limiter_1s), Depends(limiter_30m)])
async def strict_endpoint():
    return {"message": "You passed both rate limits!"}
```

---

## 🧩 Supported Algorithms

- **Fixed Window:** Simple, aggressive limits.
- **Sliding Window (Approximated):** Smoother than fixed window, more efficient than log-based.
- **Sliding Window (Log-based):** Most accurate and fair, eliminates burst issues.
- **Token Bucket:** Allows bursts, enforces average rate.
- **Leaky Bucket:** Smooths out bursts, enforces constant output rate.
- **GCRA:** Precise, fair, and burstable rate limiting.

See the [strategies overview](https://devbijay.github.io/FastAPI-Cap/strategies/overview/) for details and usage examples.

---

## ⚙️ Customization

- **Custom Key Function:** Rate limit by user ID, API key, etc.
- **Custom on_limit Handler:** Return custom responses, log events, etc.

See [Quickstart](https://devbijay.github.io/FastAPI-Cap/quickstart/) for details.

---

## 📚 Documentation

- [Quickstart Guide](https://devbijay.github.io/FastAPI-Cap/quickstart/)
- [Strategy Overview](https://devbijay.github.io/FastAPI-Cap/strategies/overview/)
- [Fixed Window](https://devbijay.github.io/FastAPI-Cap/strategies/fixed_window/)
- [Sliding Window (Approximated)](https://devbijay.github.io/FastAPI-Cap/strategies/sliding_window/)
- [Sliding Window (Log-based)](https://devbijay.github.io/FastAPI-Cap/strategies/sliding_window_log/)
- [Token Bucket](https://devbijay.github.io/FastAPI-Cap/strategies/token_bucket/)
- [Leaky Bucket](https://devbijay.github.io/FastAPI-Cap/strategies/leaky_bucket/)
- [GCRA](https://devbijay.github.io/FastAPI-Cap/strategies/gcra/)

---

## 🛡️ License

**MIT License**

---

## 🤝 Contributing

Contributions, bug reports, and feature requests are welcome!  
Please open an issue or submit a pull request.

---


