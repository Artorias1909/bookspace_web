"""Manga metadata router: read, upsert, and chapter-refresh endpoints."""
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from .. import crud, dnb, schemas
from ..deps import DbSession, CurrentUser

log = logging.getLogger("bookspace.api")
router = APIRouter()


@router.get("/{item_id}/meta", response_model=schemas.MangaVolumeRead)
async def get_manga_meta(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Return manga-specific metadata (demographic, original title, chapters) for an item."""
    manga = await crud.get_manga_volume(db, item_id)
    if not manga:
        raise HTTPException(status_code=404, detail=f"No manga metadata found for item {item_id}.")
    return manga


@router.put("/{item_id}/meta", response_model=schemas.MangaVolumeRead)
async def upsert_manga_meta(
    item_id: int,
    meta_in: schemas.MangaVolumeUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create or fully replace manga metadata (including chapters) for an item."""
    item = await crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found.")
    owned = await crud.get_user_item_by_item_id(db, current_user.id, item_id)
    if not owned:
        raise HTTPException(status_code=403, detail="You can only edit items in your own library.")
    try:
        manga = await crud.upsert_manga_volume(db, item_id, meta_in)
    except SQLAlchemyError:
        log.error("Database error upserting manga meta for item_id=%s", item_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save manga metadata. Please try again.")
    return manga


@router.post("/{item_id}/chapters/refresh", response_model=schemas.MangaVolumeRead)
async def refresh_chapters(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Re-fetch chapter data from DNB for an existing item and update its MangaVolume."""
    item = await crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found.")
    owned = await crud.get_user_item_by_item_id(db, current_user.id, item_id)
    if not owned:
        raise HTTPException(status_code=403, detail="You can only refresh items in your own library.")
    if not item.isbn:
        raise HTTPException(status_code=404, detail="Item has no ISBN; cannot fetch chapter data.")

    dnb_data = await dnb.fetch_dnb_by_isbn(item.isbn)
    chapters = dnb_data.get("chapters") if dnb_data else None
    if not chapters:
        raise HTTPException(status_code=404, detail="No chapter data available from DNB for this ISBN.")

    chapter_objs = [schemas.ChapterEntryCreate(**ch) for ch in chapters]
    meta_in = schemas.MangaVolumeCreate(chapters=chapter_objs)
    try:
        manga = await crud.upsert_manga_volume(db, item_id, meta_in)
    except SQLAlchemyError:
        log.error("Database error refreshing chapters for item_id=%s", item_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save chapter data. Please try again.")
    return manga
