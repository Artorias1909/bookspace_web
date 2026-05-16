import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..deps import get_db_session
from ..auth import get_current_user

log = logging.getLogger("bookspace.api")
router = APIRouter()


@router.get("/search", response_model=List[schemas.ItemRead])
async def search_items(
    q: Optional[str] = Query(None, min_length=1),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    if not q:
        raise HTTPException(status_code=400, detail="Search query parameter 'q' is required.")
    log.debug("Item search: q=%r limit=%s offset=%s user=%s", q, limit, offset, current_user.id)
    try:
        rows = await crud.search_items(db, q, limit, offset)
    except SQLAlchemyError:
        log.error("Database error during item search q=%r", q, exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed due to a database error.")
    log.debug("Item search q=%r → %s results", q, len(rows))
    return rows


@router.post("/", response_model=schemas.ItemRead, status_code=201)
async def create_item(
    item_in: schemas.ItemCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    log.info("Creating item '%s' (user=%s)", item_in.title, current_user.id)
    try:
        return await crud.create_item(db, item_in)
    except SQLAlchemyError:
        log.error("Database error while creating item '%s'", item_in.title, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save item. Please try again.")


@router.get("/{item_id}", response_model=schemas.ItemRead)
async def read_item(
    item_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        item = await crud.get_item(db, item_id)
    except SQLAlchemyError:
        log.error("Database error fetching item id=%s", item_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load item. Please try again.")
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found.")
    return item


@router.put("/{item_id}", response_model=schemas.ItemRead)
async def update_item(
    item_id: int,
    item_update: schemas.ItemUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        item = await crud.get_item(db, item_id)
    except SQLAlchemyError:
        log.error("Database error fetching item id=%s for update", item_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load item. Please try again.")
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found.")
    # Only the user who has this item in their library may edit its metadata.
    owned = await crud.get_user_item_by_item_id(db, current_user.id, item_id)
    if not owned:
        raise HTTPException(status_code=403, detail="You can only edit items in your own library.")
    try:
        return await crud.update_item(db, item, item_update)
    except SQLAlchemyError:
        log.error("Database error updating item id=%s", item_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save changes. Please try again.")
