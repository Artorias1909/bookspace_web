"""Simple in-memory sliding-window rate limiter (no external dependencies).

Designed as a FastAPI dependency — raises HTTP 429 when the caller exceeds
the configured limit within the rolling time window.
"""
import time
from asyncio import Lock
from collections import defaultdict

from fastapi import HTTPException, Request

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()

# Login endpoint: 10 attempts per IP per 60 seconds
LOGIN_WINDOW   = 60   # seconds
LOGIN_MAX_HITS = 10


async def login_rate_limit(request: Request) -> None:
    """FastAPI dependency: allow at most LOGIN_MAX_HITS per IP per LOGIN_WINDOW seconds."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()

    async with _lock:
        bucket = _buckets[ip]
        # Drop timestamps that have fallen outside the window
        cutoff = now - LOGIN_WINDOW
        _buckets[ip] = bucket = [t for t in bucket if t > cutoff]

        if len(bucket) >= LOGIN_MAX_HITS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many login attempts from this IP. "
                    f"Try again in {LOGIN_WINDOW} seconds."
                ),
                headers={"Retry-After": str(LOGIN_WINDOW)},
            )
        bucket.append(now)
