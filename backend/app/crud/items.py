import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas

log = logging.getLogger("bookspace.crud")

# Shared eager-load options used by all item queries
_ITEM_LOAD = [
    selectinload(models.Item.series),
    selectinload(models.Item.manga_meta).selectinload(models.MangaVolume.chapters),
]


async def create_item(db: AsyncSession, item_in: schemas.ItemCreate) -> models.Item:
    item = models.Item(**item_in.model_dump(exclude_none=True))
    db.add(item)
    await db.commit()
    await db.refresh(item)
    item_id = item.id
    log.info("Item created: '%s' (id=%s)", item.title, item_id)
    return await get_item(db, item_id)


async def get_item(db: AsyncSession, item_id: int) -> Optional[models.Item]:
    result = await db.execute(
        select(models.Item).options(*_ITEM_LOAD).where(models.Item.id == item_id)
    )
    item = result.scalars().first()
    if not item:
        log.debug("Item id=%s not found", item_id)
    return item


async def search_items(
    db: AsyncSession, q: str, limit: int = 25, offset: int = 0
) -> List[models.Item]:
    result = await db.execute(
        select(models.Item)
        .options(*_ITEM_LOAD)
        .where(models.Item.title.ilike(f"%{q}%"))
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    log.debug("search_items q=%r → %s results", q, len(rows))
    return rows


async def update_item(
    db: AsyncSession, item: models.Item, item_update: schemas.ItemUpdate
) -> models.Item:
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
    result = await db.execute(
        select(models.Item)
        .options(*_ITEM_LOAD)
        .where(models.Item.series_id == series_id)
        .order_by(models.Item.volume_number.asc().nullsfirst(), models.Item.title.asc())
    )
    rows = result.scalars().all()
    log.debug("list_series_items series_id=%s → %s items", series_id, len(rows))
    return rows
