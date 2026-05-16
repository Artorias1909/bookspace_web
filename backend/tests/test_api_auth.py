import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import Request

from tests.conftest import create_user_and_login
import app.rate_limit as _rl
import app.auth as _auth
from app.rate_limit import _get_client_ip


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/auth/register", json={"username": "newuser", "password": "pass1234"})
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate(client):
    await client.post("/auth/register", json={"username": "dup", "password": "pass1234"})
    resp = await client.post("/auth/register", json={"username": "dup", "password": "pass1234"})
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_db_error(client):
    with patch("app.routers.auth.crud.create_user", side_effect=SQLAlchemyError("db fail")):
        resp = await client.post("/auth/register", json={"username": "err", "password": "pass1234"})
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_register_race_condition_returns_400(client):
    """IntegrityError from concurrent duplicate registration → 400, not 500."""
    with patch("app.routers.auth.crud.create_user", side_effect=IntegrityError(None, None, Exception("dup"))):
        resp = await client.post("/auth/register", json={"username": "race_user", "password": "pass1234"})
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/auth/register", json={"username": "login1", "password": "pass1234"})
    resp = await client.post(
        "/auth/token",
        data={"username": "login1", "password": "pass1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_credentials(client):
    await client.post("/auth/register", json={"username": "login2", "password": "pass1234"})
    resp = await client.post(
        "/auth/token",
        data={"username": "login2", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_db_error(client):
    with patch("app.routers.auth.crud.authenticate_user", side_effect=SQLAlchemyError("db")):
        resp = await client.post(
            "/auth/token",
            data={"username": "x", "password": "y"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_me(client):
    headers = await create_user_and_login(client, "meuser", "pass1234")
    resp = await client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "meuser"


@pytest.mark.asyncio
async def test_logout_invalidates_token(client):
    """After logout the same token is rejected with 401."""
    _rl._buckets.clear()
    h = await create_user_and_login(client, "logout_user", "pass1234")
    # Confirm token is valid
    assert (await client.get("/auth/me", headers=h)).status_code == 200
    # Logout
    resp = await client.post("/auth/logout", headers=h)
    assert resp.status_code == 204
    # Token is now revoked
    assert (await client.get("/auth/me", headers=h)).status_code == 401
    _auth._revoked_jtis.clear()  # cleanup so other tests are unaffected


@pytest.mark.asyncio
async def test_login_rate_limit(client):
    """Exceeding LOGIN_MAX_HITS attempts in the window returns 429."""
    _rl._buckets.clear()
    for _ in range(_rl.LOGIN_MAX_HITS):
        await client.post(
            "/auth/token",
            data={"username": "nobody", "password": "x"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    resp = await client.post(
        "/auth/token",
        data={"username": "nobody", "password": "x"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    _rl._buckets.clear()  # cleanup so other tests are unaffected


@pytest.mark.asyncio
async def test_register_rate_limit(client):
    """Exceeding REGISTER_MAX_HITS attempts in the window returns 429."""
    _rl._buckets.clear()
    for i in range(_rl.REGISTER_MAX_HITS):
        await client.post("/auth/register", json={"username": f"rl_user_{i}", "password": "pass1234"})
    resp = await client.post("/auth/register", json={"username": "rl_overflow", "password": "pass1234"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    _rl._buckets.clear()


# ---------------------------------------------------------------------------
# _get_client_ip unit tests
# ---------------------------------------------------------------------------

def _make_request(headers=(), client=None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers],
    }
    if client is not None:
        scope["client"] = client
    return Request(scope)


def test_get_client_ip_uses_forwarded_for():
    req = _make_request(headers=[("X-Forwarded-For", "1.2.3.4, 5.6.7.8")])
    assert _get_client_ip(req) == "1.2.3.4"


def test_get_client_ip_falls_back_to_remote_addr():
    req = _make_request(client=("192.168.1.1", 12345))
    assert _get_client_ip(req) == "192.168.1.1"


def test_get_client_ip_no_client_returns_unknown():
    req = _make_request()
    assert _get_client_ip(req) == "unknown"
