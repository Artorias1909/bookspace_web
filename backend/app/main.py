"""FastAPI application factory: CORS middleware, security headers, request logging, and router mounting."""
import asyncio
import logging
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .logging_config import configure_logging
from .database import engine
from .routers import (
    auth as auth_router,
    items as items_router,
    manga as manga_router,
    series as series_router,
    user_items as user_items_router,
    import_isbn as import_router,
)

configure_logging()
log = logging.getLogger("bookspace.api")

_ALEMBIC_CFG_PATH = Path(__file__).parent.parent / "alembic.ini"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ASGI lifespan handler — run Alembic migrations on startup, log on shutdown.

    Raises:
        Exception: Re-raises any migration failure so the server refuses to start.
    """
    log.info(
        "Starting Bookspace API — env=production frontend_url=%s",
        settings.frontend_url,
    )
    try:
        alembic_cfg = AlembicConfig(str(_ALEMBIC_CFG_PATH))
        await asyncio.to_thread(alembic_command.upgrade, alembic_cfg, "head")
        log.info("Database migrations applied successfully")
    except Exception:
        log.critical("Failed to run database migrations — refusing to start", exc_info=True)
        raise
    yield
    log.info("Bookspace API shutting down")


app = FastAPI(title="Bookspace Library API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    """Reject requests whose Content-Length header exceeds 1 MB with HTTP 413."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Append OWASP-recommended HTTP security headers to every response.

    Uses setdefault so that handlers can override individual headers when needed.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; font-src 'self'; connect-src 'self'",
    )
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Access-log middleware: assigns a request ID, measures duration, logs at appropriate level.

    Every request gets an X-Request-ID response header so individual requests can be
    traced through the logs. Catches exceptions that bubble out of handlers and returns
    a generic 500 to prevent raw tracebacks leaking to clients.
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    t0 = time.perf_counter()

    log.info("→ %s %s [%s]", request.method, request.url.path, request_id)
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - t0) * 1000
        log.error(
            "✗ %s %s [%s] %.1fms — unhandled exception",
            request.method,
            request.url.path,
            request_id,
            duration_ms,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected server error occurred. Please try again."},
        )

    duration_ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = request_id
    msg = "← %s %s %s [%s] %.1fms"
    args = (request.method, request.url.path, response.status_code, request_id, duration_ms)

    if response.status_code >= 500:
        log.error(msg, *args)
    elif response.status_code >= 400:
        log.warning(msg, *args)
    else:
        log.debug(msg, *args)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all 500 handler for exceptions that escape the middleware chain."""
    log.error(
        "Uncaught %s at %s %s: %s\n%s",
        type(exc).__name__,
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again."},
    )


@app.get("/health", tags=["health"])
async def health_check():
    """Liveness probe — returns 200 OK when the server is running."""
    return {"status": "ok"}


app.include_router(auth_router.router,       prefix="/auth",       tags=["auth"])
app.include_router(items_router.router,      prefix="/items",      tags=["items"])
app.include_router(manga_router.router,      prefix="/items",      tags=["manga"])
app.include_router(series_router.router,     prefix="/series",     tags=["series"])
app.include_router(user_items_router.router, prefix="/user-items", tags=["user-items"])
app.include_router(import_router.router,     prefix="/import",     tags=["import"])
