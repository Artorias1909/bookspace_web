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

# Register endpoint: 5 attempts per IP per 60 seconds
REGISTER_WINDOW   = 60
REGISTER_MAX_HITS = 5


def _get_client_ip(request: Request) -> str:
    """Return the real client IP, preferring X-Forwarded-For set by a trusted proxy."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def login_rate_limit(request: Request) -> None:
    """FastAPI dependency: allow at most LOGIN_MAX_HITS per IP per LOGIN_WINDOW seconds."""
    ip = _get_client_ip(request)
    now = time.monotonic()

    async with _lock:
        bucket = _buckets[ip]
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


async def register_rate_limit(request: Request) -> None:
    """FastAPI dependency: allow at most REGISTER_MAX_HITS per IP per REGISTER_WINDOW seconds."""
    ip = _get_client_ip(request)
    now = time.monotonic()
    key = f"register:{ip}"

    async with _lock:
        bucket = _buckets[key]
        cutoff = now - REGISTER_WINDOW
        _buckets[key] = bucket = [t for t in bucket if t > cutoff]

        if len(bucket) >= REGISTER_MAX_HITS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many registration attempts from this IP. "
                    f"Try again in {REGISTER_WINDOW} seconds."
                ),
                headers={"Retry-After": str(REGISTER_WINDOW)},
            )
        bucket.append(now)
