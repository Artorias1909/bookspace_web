"""Auth router: user registration, JWT login, token logout, and /me profile endpoint."""
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .. import crud, schemas, auth
from ..deps import DbSession, CurrentUser
from ..rate_limit import login_rate_limit, register_rate_limit

log = logging.getLogger("bookspace.auth")
router = APIRouter()


@router.post("/register", response_model=schemas.UserRead, status_code=201, dependencies=[Depends(register_rate_limit)])
async def register(user_in: schemas.UserCreate, db: DbSession):
    """Create a new user account; 400 if the username is taken, rate-limited to 5 attempts/min/IP."""
    log.info("Registration attempt for username '%s'", user_in.username)
    existing = await crud.get_user_by_username(db, user_in.username)
    if existing:
        log.warning("Registration rejected — username '%s' already exists", user_in.username)
        raise HTTPException(status_code=400, detail="Username already registered.")
    try:
        user = await crud.create_user(db, user_in)
    except IntegrityError:
        log.warning("Concurrent registration conflict for username '%s'", user_in.username)
        raise HTTPException(status_code=400, detail="Username already registered.")
    except SQLAlchemyError:
        log.error("Database error while creating user '%s'", user_in.username, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create user. Please try again.")
    return user


@router.post("/token", response_model=schemas.Token, dependencies=[Depends(login_rate_limit)])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: DbSession = None,
):
    """Exchange credentials for a JWT bearer token; 401 on bad credentials, rate-limited to 10/min/IP."""
    log.info("Login attempt for username '%s'", form_data.username)
    try:
        user = await crud.authenticate_user(db, form_data.username, form_data.password)
    except SQLAlchemyError:
        log.error("Database error during authentication for '%s'", form_data.username, exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication service unavailable. Please try again.")

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = auth.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    log.info("Login successful for username '%s'", user.username)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=204)
async def logout(
    token: str = Depends(auth.oauth2_scheme),
    _: CurrentUser = None,
):
    """Invalidate the current access token via server-side JTI revocation."""
    auth.revoke_token(token)


@router.get("/me", response_model=schemas.UserRead)
async def read_users_me(current_user: CurrentUser):
    """Return the profile of the currently authenticated user."""
    return current_user
