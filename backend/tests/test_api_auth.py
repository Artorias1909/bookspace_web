import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.exc import SQLAlchemyError

from tests.conftest import create_user_and_login
import app.rate_limit as _rl


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
