"""
FastAPI Cap: A robust, extensible rate limiting library for FastAPI.

This package provides multiple rate limiting strategies, all backed by Redis,
and designed for easy integration with FastAPI applications.

Available limiters:
- RateLimiter: Fixed window rate limiting.
- SlidingWindowRateLimiter: Sliding window counter.
- TokenBucketRateLimiter: Token bucket algorithm.
- LeakyBucketRateLimiter: Leaky bucket algorithm.
- GCRARateLimiter: Generalized Cell Rate Algorithm (GCRA).
- SlidingWindowLogRateLimiter: Precise sliding window log algorithm.

Usage:
    from fastapicap import RateLimiter, SlidingWindowRateLimiter, ...

"""

from .strategy.fixed_window import RateLimiter
from .strategy.sliding_window import SlidingWindowRateLimiter
from .strategy.token_bucket import TokenBucketRateLimiter
from .strategy.leaky_bucket import LeakyBucketRateLimiter
from .strategy.gcra import GCRARateLimiter
from .strategy.sliding_window_log import SlidingWindowLogRateLimiter
from .connection import Cap

__all__ = [
    "Cap",
    "RateLimiter",
    "TokenBucketRateLimiter",
    "SlidingWindowRateLimiter",
    "LeakyBucketRateLimiter",
    "GCRARateLimiter",
    "SlidingWindowLogRateLimiter",
]
