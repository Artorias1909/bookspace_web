import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .logging_config import configure_logging
from .database import engine, Base
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Bookspace API — initialising database schema")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Database schema ready")
    except Exception:
        log.critical("Failed to initialise database schema", exc_info=True)
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
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
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
    log.info("%s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        log.error(
            "Unhandled exception during %s %s",
            request.method,
            request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected server error occurred. Please try again."},
        )
    if response.status_code >= 500:
        log.error("%s %s → %s", request.method, request.url.path, response.status_code)
    elif response.status_code >= 400:
        log.warning("%s %s → %s", request.method, request.url.path, response.status_code)
    else:
        log.debug("%s %s → %s", request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
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


app.include_router(auth_router.router,       prefix="/auth",       tags=["auth"])
app.include_router(items_router.router,      prefix="/items",      tags=["items"])
app.include_router(manga_router.router,      prefix="/items",      tags=["manga"])
app.include_router(series_router.router,     prefix="/series",     tags=["series"])
app.include_router(user_items_router.router, prefix="/user-items", tags=["user-items"])
app.include_router(import_router.router,     prefix="/import",     tags=["import"])
