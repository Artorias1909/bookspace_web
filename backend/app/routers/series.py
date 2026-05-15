import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..deps import get_db_session
from ..auth import get_current_user

log = logging.getLogger("bookspace.api")
router = APIRouter()


@router.post("/", response_model=schemas.SeriesRead, status_code=201)
async def create_series(
    series_in: schemas.SeriesCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    log.info("Creating series '%s' (user=%s)", series_in.name, current_user.id)
    try:
        return await crud.create_series(db, series_in)
    except SQLAlchemyError:
        log.error("Database error creating series '%s'", series_in.name, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create series. Please try again.")


@router.get("/", response_model=List[schemas.SeriesRead])
async def read_series(
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        return await crud.list_series(db)
    except SQLAlchemyError:
        log.error("Database error listing series", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series list. Please try again.")


@router.get("/{series_id}", response_model=schemas.SeriesRead)
async def get_series(
    series_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if series is None:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    return series


@router.put("/{series_id}", response_model=schemas.SeriesRead)
async def update_series(
    series_id: int,
    series_in: schemas.SeriesCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s for update", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if not series:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    try:
        series.name = series_in.name
        series.type = series_in.type
        series.total_volumes = series_in.total_volumes
        db.add(series)
        await db.commit()
        await db.refresh(series)
        log.info("Series id=%s updated: '%s'", series_id, series.name)
    except SQLAlchemyError:
        log.error("Database error updating series id=%s", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save changes. Please try again.")
    return series


@router.post("/{series_id}/assign/{item_id}", response_model=schemas.ItemRead)
async def assign_item(
    series_id: int,
    item_id: int,
    volume_number: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s for assignment", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if not series:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    try:
        item = await crud.assign_item_to_series(db, item_id, series_id, volume_number)
    except SQLAlchemyError:
        log.error("Database error assigning item id=%s to series id=%s", item_id, series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not assign item. Please try again.")
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found.")
    return item


@router.get("/{series_id}/items", response_model=List[schemas.ItemRead])
async def series_items(
    series_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s for item list", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if not series:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    try:
        return await crud.list_series_items(db, series_id)
    except SQLAlchemyError:
        log.error("Database error listing items for series id=%s", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series items. Please try again.")
