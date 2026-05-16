import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas

log = logging.getLogger("bookspace.crud")


async def create_box_set(
    db: AsyncSession,
    series_id: Optional[int],
    name: Optional[str],
    isbn: str,
    volume_from: int,
    volume_to: int,
    cover_url: Optional[str] = None,
    publication_year: Optional[int] = None,
) -> models.BoxSet:
    box = models.BoxSet(
        series_id=series_id,
        name=name,
        isbn=isbn,
        volume_from=volume_from,
        volume_to=volume_to,
        cover_url=cover_url,
        publication_year=publication_year,
    )
    db.add(box)
    await db.commit()
    await db.refresh(box)
    log.info(
        "BoxSet created: '%s' id=%s series_id=%s vol=%s-%s",
        name, box.id, series_id, volume_from, volume_to,
    )
    return box


async def get_box_set_by_isbn(db: AsyncSession, isbn: str) -> Optional[models.BoxSet]:
    result = await db.execute(
        select(models.BoxSet).where(models.BoxSet.isbn == isbn)
    )
    return result.scalars().first()


async def find_or_create_volume_item(
    db: AsyncSession,
    series_id: int,
    series_name: str,
    volume_number: int,
    media_type: str,
    authors: List[str],
    publication_year: Optional[int],
    box_set_id: Optional[int] = None,
) -> models.Item:
    """Return the existing Item for series+volume, or create a placeholder. Links to box_set."""
    from .items import get_item, _ITEM_LOAD

    result = await db.execute(
        select(models.Item)
        .options(*_ITEM_LOAD)
        .where(
            models.Item.series_id == series_id,
            models.Item.volume_number == str(volume_number),
        )
    )
    item = result.scalars().first()
    if item:
        if box_set_id is not None and item.box_set_id != box_set_id:
            item.box_set_id = box_set_id
            db.add(item)
            await db.commit()
            item = await get_item(db, item.id)
        return item

    # Create minimal placeholder — user can scan individual ISBN later for full data
    new_item = models.Item(
        title=f"{series_name} Band {volume_number}",
        authors=authors,
        media_type=media_type,
        series_id=series_id,
        volume_number=str(volume_number),
        publication_year=publication_year,
        box_set_id=box_set_id,
    )
    db.add(new_item)
    await db.commit()
    item = await get_item(db, new_item.id)
    log.info(
        "Placeholder volume created: '%s' (id=%s series_id=%s vol=%s)",
        new_item.title, item.id, series_id, volume_number,
    )
    return item
