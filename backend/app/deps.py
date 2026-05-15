"""FastAPI dependency aliases.

Import these in routers instead of the full Depends(...) expressions
to keep endpoint signatures concise.
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from . import schemas
from .auth import get_current_user

# Re-export get_db under the old alias (used in conftest.py overrides)
get_db_session = get_db

# Annotated shorthands for common dependencies
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[schemas.UserRead, Depends(get_current_user)]
