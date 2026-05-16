"""Series router: CRUD, bulk status updates, item assignment, and library deletion."""
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
    """Create a new series record; requires authentication."""
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
    """List all series records (up to the default limit); requires authentication."""
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
    """Fetch a single series by ID; 404 if not found."""
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
    """Replace series metadata; only users who own at least one volume in it may edit; 403 otherwise."""
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s for update", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if not series:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    if not await crud.user_owns_series(db, current_user.id, series_id):
        raise HTTPException(status_code=403, detail="You can only edit series in your own library.")
    try:
        series.name = series_in.name
        series.type = series_in.type
        series.total_volumes = series_in.total_volumes
        series.cover_url = series_in.cover_url
        db.add(series)
        await db.commit()
        await db.refresh(series)
        log.info("Series id=%s updated: '%s'", series_id, series.name)
    except SQLAlchemyError:
        log.error("Database error updating series id=%s", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save changes. Please try again.")
    return series


@router.patch("/{series_id}/status", response_model=schemas.BulkUpdateResult)
async def bulk_set_series_status(
    series_id: int,
    update_in: schemas.SeriesStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    """Set all of the current user's library entries for a series to the given status."""
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s for bulk status", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if not series:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    try:
        count = await crud.bulk_update_series_status(db, current_user.id, series_id, update_in.status)
    except SQLAlchemyError:
        log.error("Database error bulk-updating status for series id=%s", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not update status. Please try again.")
    return schemas.BulkUpdateResult(updated=count)


@router.post("/{series_id}/assign/{item_id}", response_model=schemas.ItemRead)
async def assign_item(
    series_id: int,
    item_id: int,
    volume_number: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    """Assign a catalog item to a series with an optional volume number; item must be in caller's library."""
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s for assignment", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if not series:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    owned = await crud.get_user_item_by_item_id(db, current_user.id, item_id)
    if not owned:
        raise HTTPException(status_code=403, detail="You can only assign items in your own library.")
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
    """Return all catalog items belonging to a series, ordered by volume number."""
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


@router.delete("/{series_id}/library", response_model=schemas.BulkUpdateResult)
async def delete_series_from_library(
    series_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    """Remove all of the current user's library entries for a series."""
    try:
        series = await crud.get_series(db, series_id)
    except SQLAlchemyError:
        log.error("Database error fetching series id=%s for delete", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load series. Please try again.")
    if not series:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found.")
    try:
        count = await crud.delete_user_series_entries(db, current_user.id, series_id)
    except SQLAlchemyError:
        log.error("Database error deleting library entries for series id=%s", series_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not delete series entries. Please try again.")
    log.info("Series id=%s removed from library of user_id=%s (%s entries)", series_id, current_user.id, count)
    return schemas.BulkUpdateResult(updated=count)

