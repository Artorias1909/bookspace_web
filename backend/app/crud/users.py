import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas, auth

log = logging.getLogger("bookspace.crud")


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.username == username))
    return result.scalars().first()


async def create_user(db: AsyncSession, user_in: schemas.UserCreate) -> models.User:
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
    user = await get_user_by_username(db, username)
    if not user:
        log.warning("Login failed — unknown user '%s'", username)
        return None
    if not auth.verify_password(password, user.hashed_password):
        log.warning("Login failed — wrong password for user '%s'", username)
        return None
    log.info("User '%s' authenticated successfully", username)
    return user
