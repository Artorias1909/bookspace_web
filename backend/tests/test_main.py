"""
Tests for main.py: middleware logging, global exception handler,
lifespan startup, and logging_config.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import Request
from fastapi.responses import JSONResponse

from app.main import app, log_requests, unhandled_exception_handler, security_headers, limit_request_body
from app.logging_config import configure_logging


# ---------------------------------------------------------------------------
# logging_config
# ---------------------------------------------------------------------------

def test_configure_logging_runs_without_error():
    configure_logging()  # must not raise


@pytest.mark.asyncio
async def test_get_db_yields_session():
    """Covers the get_db generator body in database.py."""
    from app.database import get_db, AsyncSessionLocal
    gen = get_db()
    session = await gen.__anext__()
    assert session is not None
    try:
        await gen.aclose()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Middleware: log_requests
# ---------------------------------------------------------------------------

def _make_request(method="GET", path="/test"):
    scope = {"type": "http", "method": method, "path": path, "headers": []}
    request = Request(scope)
    return request


@pytest.mark.asyncio
async def test_middleware_2xx(client):
    """A normal 200 response is logged at DEBUG level."""
    resp = await client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_middleware_4xx_logged_as_warning(client):
    """A 401 response triggers the warning log branch."""
    resp = await client.get("/user-items/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_middleware_5xx_logged_as_error(client):
    """An endpoint that raises triggers the 500 error log branch."""
    from app.main import app as _app

    @_app.get("/test-server-error")
    async def _crash():
        raise RuntimeError("intentional crash")

    try:
        resp = await client.get("/test-server-error")
        assert resp.status_code == 500
    finally:
        # Remove the test route to avoid affecting other tests
        _app.routes[:] = [r for r in _app.routes if getattr(r, "path", None) != "/test-server-error"]


@pytest.mark.asyncio
async def test_middleware_catches_call_next_exception():
    """The middleware's except block fires when call_next itself raises."""
    request = _make_request()

    async def crashing_next(req):
        raise RuntimeError("call_next exploded")

    response = await log_requests(request, crashing_next)
    assert response.status_code == 500
    import json
    body = json.loads(response.body)
    assert "unexpected" in body["detail"].lower()


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_headers_present(client):
    """Every response should carry the security headers."""
    resp = await client.get("/docs")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-xss-protection") == "1; mode=block"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "content-security-policy" in resp.headers


@pytest.mark.asyncio
async def test_security_headers_middleware_directly():
    """Unit-test the middleware function in isolation."""
    request = _make_request()
    mock_response = MagicMock()
    mock_response.headers = {}

    async def fake_next(req):
        return mock_response

    result = await security_headers(request, fake_next)
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in result.headers


# ---------------------------------------------------------------------------
# Body size middleware
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_limit_request_body_rejects_large_payload():
    """Middleware returns 413 when Content-Length exceeds 1 MB."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-length", b"2097152")],  # 2 MB
    }
    request = Request(scope)

    async def fake_next(req):
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True})

    response = await limit_request_body(request, fake_next)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_limit_request_body_allows_normal_payload():
    """A request without Content-Length passes through the middleware."""
    request = _make_request()

    async def fake_next(req):
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True})

    response = await limit_request_body(request, fake_next)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_global_exception_handler():
    request = _make_request()
    exc = RuntimeError("unhandled boom")
    response = await unhandled_exception_handler(request, exc)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /health returns 200 with status ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Lifespan: DB failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lifespan_success():
    """Covers the happy-path lifespan: Alembic upgrade succeeds, yield, shutdown."""
    from app.main import lifespan

    with patch("app.main.alembic_command.upgrade") as mock_upgrade:
        async with lifespan(app):
            pass  # yield point; after this block the shutdown log runs

    mock_upgrade.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_db_failure():
    """Covers the failure path: Alembic upgrade raises, lifespan re-raises."""
    from app.main import lifespan

    with patch("app.main.alembic_command.upgrade", side_effect=RuntimeError("DB unreachable")):
        with pytest.raises(RuntimeError, match="DB unreachable"):
            async with lifespan(app):
                pass  # pragma: no cover
