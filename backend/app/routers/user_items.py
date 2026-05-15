import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..deps import get_db_session
from ..auth import get_current_user

log = logging.getLogger("bookspace.api")
router = APIRouter()


@router.post("/", response_model=schemas.UserItemDataRead, status_code=201)
async def create_user_item(
    entry_in: schemas.UserItemDataCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    log.info("Adding library entry for user=%s", current_user.id)
    try:
        entry = await crud.create_user_item_data(db, current_user.id, entry_in)
    except ValueError as exc:
        log.warning("Invalid data for create_user_item user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError:
        log.error("Database error creating library entry for user=%s", current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not add to library. Please try again.")
    return entry


@router.get("/", response_model=schemas.PagedResponse[schemas.UserItemDataRead])
async def list_user_items(
    q: Optional[str] = Query(None, min_length=1),
    status: Optional[str] = Query(None, pattern="^(unread|reading|completed|owned|wishlist)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("title", pattern="^(title|author|publication_year|status)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    log.debug(
        "list_user_items user=%s page=%s size=%s sort=%s/%s q=%r status=%r",
        current_user.id, page, page_size, sort_by, sort_dir, q, status,
    )
    try:
        items = await crud.list_user_items(db, current_user.id, page, page_size, sort_by, sort_dir, q, status)
        total = await crud.count_user_items(db, current_user.id, q, status)
    except SQLAlchemyError:
        log.error("Database error listing items for user=%s", current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load library. Please try again.")
    return schemas.PagedResponse.build(items=items, total=total, page=page, page_size=page_size)


@router.get("/{entry_id}", response_model=schemas.UserItemDataRead)
async def get_user_item(
    entry_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        entry = await crud.get_user_item(db, entry_id, current_user.id)
    except SQLAlchemyError:
        log.error("Database error fetching entry id=%s for user=%s", entry_id, current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load entry. Please try again.")
    if not entry:
        raise HTTPException(status_code=404, detail=f"Library entry {entry_id} not found.")
    return entry


@router.put("/{entry_id}", response_model=schemas.UserItemDataRead)
async def update_user_item(
    entry_id: int,
    entry_update: schemas.UserItemDataUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        entry = await crud.get_user_item(db, entry_id, current_user.id)
    except SQLAlchemyError:
        log.error("Database error fetching entry id=%s for update user=%s", entry_id, current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load entry. Please try again.")
    if not entry:
        raise HTTPException(status_code=404, detail=f"Library entry {entry_id} not found.")
    try:
        return await crud.update_user_item_data(db, entry, entry_update)
    except SQLAlchemyError:
        log.error("Database error updating entry id=%s", entry_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save changes. Please try again.")
