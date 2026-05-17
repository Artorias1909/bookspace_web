"""Application settings loaded from environment variables (and optional .env file)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Immutable application configuration derived from environment variables.

    Attributes:
        database_url: Async-compatible PostgreSQL connection string (asyncpg dialect).
        secret_key: HMAC secret used to sign JWT tokens; must stay private.
        algorithm: JWT signing algorithm, always HS256.
        access_token_expire_minutes: Lifetime of issued access tokens.
        google_books_api_key: Optional Books API key; empty string uses shared quota.
        frontend_url: Allowed CORS origin for the React frontend.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    google_books_api_key: str = ""
    frontend_url: str = "http://localhost:3000"


settings = Settings()
