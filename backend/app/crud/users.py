"""User lookup, creation, and credential verification against the database."""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas, auth

log = logging.getLogger("bookspace.crud")


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
    """Return the User with the given username, or None if not found."""
    result = await db.execute(select(models.User).where(models.User.username == username))
    return result.scalars().first()


async def create_user(db: AsyncSession, user_in: schemas.UserCreate) -> models.User:
    """Hash the password, persist a new User row, and return the refreshed instance."""
    hashed_password = auth.get_password_hash(user_in.password)
    user = models.User(username=user_in.username, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("User created: '%s' (id=%s)", user.username, user.id)
    return user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[models.User]:
    """Verify username and bcrypt-hashed password; return the User on success or None on failure."""
    user = await get_user_by_username(db, username)
    if not user:
        log.warning("Login failed — unknown user '%s'", username)
        return None
    if not auth.verify_password(password, user.hashed_password):
        log.warning("Login failed — wrong password for user '%s'", username)
        return None
    log.info("User '%s' authenticated successfully", username)
    return user
