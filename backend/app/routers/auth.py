import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas, auth
from ..deps import get_db_session

log = logging.getLogger("bookspace.auth")
router = APIRouter()


@router.post("/register", response_model=schemas.UserRead, status_code=201)
async def register(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db_session)):
    log.info("Registration attempt for username '%s'", user_in.username)
    existing = await crud.get_user_by_username(db, user_in.username)
    if existing:
        log.warning("Registration rejected — username '%s' already exists", user_in.username)
        raise HTTPException(status_code=400, detail="Username already registered.")
    try:
        user = await crud.create_user(db, user_in)
    except SQLAlchemyError:
        log.error("Database error while creating user '%s'", user_in.username, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create user. Please try again.")
    return user


@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
):
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


@router.get("/me", response_model=schemas.UserRead)
async def read_users_me(current_user: schemas.UserRead = Depends(auth.get_current_user)):
    return current_user
