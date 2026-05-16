"""Async SQLAlchemy engine, session factory, and FastAPI dependency for DB access."""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url, future=True, echo=False, pool_pre_ping=True
)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped AsyncSession for the duration of a single request."""
    async with AsyncSessionLocal() as session:
        yield session
