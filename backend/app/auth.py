"""JWT-based authentication utilities: password hashing, token creation, revocation, and user resolution."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as _jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud, schemas
from .config import settings
from .database import get_db

log = logging.getLogger("bookspace.auth")

# Module-level aliases so tests can access these without importing config directly
SECRET_KEY = settings.secret_key
ALGORITHM  = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

# bcrypt with work factor 12 (OWASP minimum recommendation)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# In-memory set of revoked JWT IDs. Resets on server restart (acceptable for
# a single-instance deployment; replace with Redis for multi-instance/HA).
_revoked_jtis: set[str] = set()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash.

    Any unexpected passlib exception is caught and logged, returning False
    to avoid leaking error details to callers.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        log.error("Password verification raised an unexpected error", exc_info=True)
        return False


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with bcrypt at work factor 12 (OWASP minimum)."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Build a signed HS256 JWT containing the given claims plus `exp` and `jti`.

    Args:
        data: Claims to embed (must include ``sub`` for the username).
        expires_delta: Custom lifetime; falls back to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    to_encode["jti"] = str(uuid.uuid4())
    token = _jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    log.debug(
        "Access token created for '%s', expires in %s min",
        data.get("sub"),
        settings.access_token_expire_minutes,
    )
    return token


def revoke_token(token: str) -> None:
    """Add the token's JTI to the revocation set. No-op for invalid/expired tokens."""
    try:
        payload = _jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        jti = payload.get("jti")
        if jti:
            _revoked_jtis.add(jti)
    except _jwt.PyJWTError:
        pass


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> schemas.UserRead:
    """FastAPI dependency: decode JWT, reject revoked tokens, and resolve the user from DB.

    Raises:
        HTTPException 401: When the token is missing, malformed, expired, revoked,
            or references an unknown user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = _jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            log.warning("JWT token missing 'sub' claim")
            raise credentials_exception
        jti = payload.get("jti")
        if jti and jti in _revoked_jtis:
            log.warning("JWT with revoked JTI '%s' was presented", jti)
            raise credentials_exception
    except _jwt.PyJWTError as exc:
        log.warning("JWT decode failed: %s", exc)
        raise credentials_exception

    user = await crud.get_user_by_username(db, username=username)
    if user is None:
        log.warning("JWT references unknown user '%s'", username)
        raise credentials_exception

    log.debug("Authenticated user '%s'", username)
    return user
