"""Application settings loaded once from environment variables at import time."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration derived from environment variables.

    Attributes:
        database_url: Async-compatible PostgreSQL connection string (asyncpg dialect).
        secret_key: HMAC secret used to sign JWT tokens; must stay private.
        algorithm: JWT signing algorithm, always HS256.
        access_token_expire_minutes: Lifetime of issued access tokens.
        google_books_api_key: Optional Books API key; empty string uses shared quota.
        frontend_url: Allowed CORS origin for the React frontend.
    """
    database_url: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    google_books_api_key: str
    frontend_url: str


def _load() -> Settings:
    """Construct Settings from environment variables.

    Raises:
        ValueError: When DATABASE_URL or SECRET_KEY are not set.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:  # pragma: no cover
        raise ValueError("DATABASE_URL environment variable is required")
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:  # pragma: no cover
        raise ValueError("SECRET_KEY environment variable is required")
    return Settings(
        database_url=database_url,
        secret_key=secret_key,
        algorithm="HS256",
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        google_books_api_key=os.getenv("GOOGLE_BOOKS_API_KEY", ""),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
    )


settings = _load()
