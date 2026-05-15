import logging
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        log.error("Password verification raised an unexpected error", exc_info=True)
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    token = _jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    log.debug(
        "Access token created for '%s', expires in %s min",
        data.get("sub"),
        settings.access_token_expire_minutes,
    )
    return token


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> schemas.UserRead:
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
    except _jwt.PyJWTError as exc:
        log.warning("JWT decode failed: %s", exc)
        raise credentials_exception

    user = await crud.get_user_by_username(db, username=username)
    if user is None:
        log.warning("JWT references unknown user '%s'", username)
        raise credentials_exception

    log.debug("Authenticated user '%s'", username)
    return user
