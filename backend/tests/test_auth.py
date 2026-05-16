import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, AsyncMock

import jwt
from fastapi import HTTPException

from app import auth as auth_module, schemas


SECRET = auth_module.SECRET_KEY
ALGO = auth_module.ALGORITHM


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def test_hash_and_verify_correct():
    hashed = auth_module.get_password_hash("mypassword")
    assert auth_module.verify_password("mypassword", hashed)


def test_verify_wrong_password():
    hashed = auth_module.get_password_hash("correct")
    assert not auth_module.verify_password("wrong", hashed)


def test_verify_password_internal_exception():
    with patch.object(auth_module.pwd_context, "verify", side_effect=Exception("crash")):
        assert auth_module.verify_password("x", "y") is False


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def test_create_access_token_with_delta():
    token = auth_module.create_access_token({"sub": "alice"}, expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, SECRET, algorithms=[ALGO])
    assert payload["sub"] == "alice"


def test_create_access_token_default_expiry():
    token = auth_module.create_access_token({"sub": "bob"})
    payload = jwt.decode(token, SECRET, algorithms=[ALGO])
    assert payload["sub"] == "bob"


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

async def _call_get_current_user(token: str, db_user=None):
    mock_db = AsyncMock()
    with patch("app.auth.crud.get_user_by_username", return_value=db_user):
        return await auth_module.get_current_user(token=token, db=mock_db)


@pytest.mark.asyncio
async def test_get_current_user_valid():
    token = auth_module.create_access_token({"sub": "carol"})
    mock_user = MagicMock(spec=schemas.UserRead)
    result = await _call_get_current_user(token, db_user=mock_user)
    assert result is mock_user


@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        await _call_get_current_user("not.a.valid.token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_missing_sub():
    token = auth_module.create_access_token({})  # no "sub" key
    with pytest.raises(HTTPException) as exc_info:
        await _call_get_current_user(token)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_unknown_user():
    token = auth_module.create_access_token({"sub": "ghost"})
    with pytest.raises(HTTPException) as exc_info:
        await _call_get_current_user(token, db_user=None)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------

def test_revoke_token_adds_jti():
    token = auth_module.create_access_token({"sub": "alice"})
    auth_module.revoke_token(token)
    payload = jwt.decode(token, SECRET, algorithms=[ALGO])
    assert payload["jti"] in auth_module._revoked_jtis
    auth_module._revoked_jtis.discard(payload["jti"])  # cleanup


def test_revoke_token_invalid_token_is_noop():
    before = len(auth_module._revoked_jtis)
    auth_module.revoke_token("not.a.valid.token")
    assert len(auth_module._revoked_jtis) == before


def test_revoke_token_no_jti_is_noop():
    # Manually encode a token without a JTI claim
    token = jwt.encode(
        {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        SECRET,
        algorithm=ALGO,
    )
    before = len(auth_module._revoked_jtis)
    auth_module.revoke_token(token)
    assert len(auth_module._revoked_jtis) == before


@pytest.mark.asyncio
async def test_get_current_user_revoked_jti():
    token = auth_module.create_access_token({"sub": "alice"})
    payload = jwt.decode(token, SECRET, algorithms=[ALGO])
    jti = payload["jti"]
    auth_module._revoked_jtis.add(jti)
    try:
        mock_user = MagicMock(spec=schemas.UserRead)
        with pytest.raises(HTTPException) as exc_info:
            await _call_get_current_user(token, db_user=mock_user)
        assert exc_info.value.status_code == 401
    finally:
        auth_module._revoked_jtis.discard(jti)
