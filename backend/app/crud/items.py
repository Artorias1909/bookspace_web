"""Catalog Item CRUD with eager-loading of series, manga_meta, and box_set relations."""
import logging
from typing import List, Optional

from sqlalchemy import select, or_, func, String, case, cast, Float
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas

log = logging.getLogger("bookspace.crud")

# Shared eager-load options used by all item queries
_ITEM_LOAD = [
    selectinload(models.Item.series),
    selectinload(models.Item.manga_meta).selectinload(models.MangaVolume.chapters),
    selectinload(models.Item.box_set),
]


async def create_item(db: AsyncSession, item_in: schemas.ItemCreate) -> models.Item:
    """Persist a new Item row and return it with all relations eager-loaded."""
    item = models.Item(**item_in.model_dump(exclude_none=True))
    db.add(item)
    await db.commit()
    await db.refresh(item)
    item_id = item.id
    log.info("Item created: '%s' (id=%s)", item.title, item_id)
    return await get_item(db, item_id)


async def get_item(db: AsyncSession, item_id: int) -> Optional[models.Item]:
    """Fetch an Item by primary key with series, manga_meta, and box_set eager-loaded, or None."""
    result = await db.execute(
        select(models.Item).options(*_ITEM_LOAD).where(models.Item.id == item_id)
    )
    item = result.scalars().first()
    if not item:
        log.debug("Item id=%s not found", item_id)
    return item


async def get_item_by_isbn(db: AsyncSession, isbn: str) -> Optional[models.Item]:
    """Find an Item by its ISBN with all relations eager-loaded, or None."""
    result = await db.execute(
        select(models.Item).options(*_ITEM_LOAD).where(models.Item.isbn == isbn)
    )
    return result.scalars().first()


async def search_items(
    db: AsyncSession, q: str, limit: int = 25, offset: int = 0
) -> List[models.Item]:
    """Case-insensitive ILIKE search across title, authors JSONB, genre, and volume_title."""
    pattern = f"%{q}%"
    result = await db.execute(
        select(models.Item)
        .options(*_ITEM_LOAD)
        .where(
            or_(
                models.Item.title.ilike(pattern),
                func.cast(models.Item.authors, String).ilike(pattern),
                models.Item.genre.ilike(pattern),
                models.Item.volume_title.ilike(pattern),
            )
        )
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    log.debug("search_items q=%r → %s results", q, len(rows))
    return rows


async def update_item(
    db: AsyncSession, item: models.Item, item_update: schemas.ItemUpdate
) -> models.Item:
    """Apply changed fields from item_update to the ORM instance and return the refreshed item."""
    changes = item_update.model_dump(exclude_unset=True)
    item_id = item.id
    for key, value in changes.items():
        setattr(item, key, value)
    db.add(item)
    await db.commit()
    log.info("Item id=%s updated: fields=%s", item_id, list(changes.keys()))
    return await get_item(db, item_id)


async def assign_item_to_series(
    db: AsyncSession,
    item_id: int,
    series_id: int,
    volume_number: Optional[str] = None,
) -> Optional[models.Item]:
    """Set series_id (and optionally volume_number) on an Item; returns None if item not found."""
    item = await get_item(db, item_id)
    if not item:
        log.warning("assign_item_to_series: item id=%s not found", item_id)
        return None
    item.series_id = series_id
    if volume_number is not None:
        item.volume_number = volume_number
    db.add(item)
    await db.commit()
    log.info("Item id=%s assigned to series id=%s (vol=%s)", item_id, series_id, volume_number)
    return await get_item(db, item_id)


async def list_series_items(db: AsyncSession, series_id: int) -> List[models.Item]:
    """Return all Items in a series ordered by volume_number ascending (NULLs first), then title.

    volume_number is stored as VARCHAR; cast to FLOAT for correct numeric ordering
    so that "10" sorts after "9" instead of before "2".
    """
    numeric_vol = case(
        (models.Item.volume_number.is_(None), None),
        else_=cast(models.Item.volume_number, Float),
    )
    result = await db.execute(
        select(models.Item)
        .options(*_ITEM_LOAD)
        .where(models.Item.series_id == series_id)
        .order_by(numeric_vol.asc().nullsfirst(), models.Item.title.asc())
    )
    rows = result.scalars().all()
    log.debug("list_series_items series_id=%s → %s items", series_id, len(rows))
    return rows
