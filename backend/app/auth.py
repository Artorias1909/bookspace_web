import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as _jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud, schemas
from .database import get_db

log = logging.getLogger("bookspace.auth")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:  # pragma: no cover
    raise ValueError("SECRET_KEY environment variable is required")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

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
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = _jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    log.debug("Access token created for subject '%s', expires in %s min", data.get("sub"), ACCESS_TOKEN_EXPIRE_MINUTES)
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
        payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
