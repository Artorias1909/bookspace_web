"""User-library router: add, list, read, update, and remove personal library entries."""
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
    """Add an item to the authenticated user's library; 409 if the item is already present."""
    log.info("Adding library entry for user=%s", current_user.id)
    try:
        entry = await crud.create_user_item_data(db, current_user.id, entry_in)
    except ValueError as exc:
        msg = str(exc)
        if msg == "already_in_library":
            raise HTTPException(status_code=409, detail="Dieses Buch ist bereits in deiner Bibliothek.")
        log.warning("Invalid data for create_user_item user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=400, detail=msg)
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
    """Return a paginated, filtered, and sorted view of the authenticated user's library."""
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
    """Fetch a single library entry by ID; 404 if not found or not owned by the caller."""
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
    """Update reading status and/or current page for a library entry; recalculates progress_percent."""
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


@router.delete("/{entry_id}", status_code=204)
async def delete_user_item(
    entry_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    """Remove a library entry from the user's library; 204 on success, 404 if not found."""
    try:
        entry = await crud.get_user_item(db, entry_id, current_user.id)
    except SQLAlchemyError:
        log.error("Database error fetching entry id=%s for delete user=%s", entry_id, current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load entry. Please try again.")
    if not entry:
        raise HTTPException(status_code=404, detail=f"Library entry {entry_id} not found.")
    try:
        await crud.delete_user_item(db, entry)
    except SQLAlchemyError:
        log.error("Database error deleting entry id=%s", entry_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not delete entry. Please try again.")
