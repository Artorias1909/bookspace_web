import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas

log = logging.getLogger("bookspace.crud")

_MANGA_SCALAR_FIELDS = (
    "original_title",
    "romanized_title",
    "demographic",
    "reading_direction",
    "dnb_id",
    "animexx_id",
)


async def get_manga_volume(db: AsyncSession, item_id: int) -> Optional[models.MangaVolume]:
    result = await db.execute(
        select(models.MangaVolume)
        .options(selectinload(models.MangaVolume.chapters))
        .where(models.MangaVolume.item_id == item_id)
    )
    return result.scalars().first()


async def upsert_manga_volume(
    db: AsyncSession,
    item_id: int,
    meta_in: schemas.MangaVolumeCreate,
) -> models.MangaVolume:
    """Create or fully replace the MangaVolume (and its chapters) for an item."""
    existing = await get_manga_volume(db, item_id)

    if existing:
        for field in _MANGA_SCALAR_FIELDS:
            val = getattr(meta_in, field, None)
            if val is not None:
                setattr(existing, field, val)
        manga = existing
        log.info("MangaVolume updated for item_id=%s", item_id)
    else:
        manga = models.MangaVolume(
            item_id=item_id,
            **{f: getattr(meta_in, f, None) for f in _MANGA_SCALAR_FIELDS},
        )
        db.add(manga)
        await db.flush()  # obtain manga.id before inserting chapters
        log.info("MangaVolume created for item_id=%s", item_id)

    if meta_in.chapters is not None:
        if existing is None:
            # Collection is unloaded on a brand-new manga — insert directly to avoid
            # an implicit lazy load on the async session.
            for ch_in in meta_in.chapters:
                db.add(models.ChapterEntry(manga_volume_id=manga.id, **ch_in.model_dump()))
        else:
            # Collection already loaded by get_manga_volume above — clear and refill
            # so the delete-orphan cascade fires and the identity map stays consistent.
            manga.chapters.clear()
            for ch_in in meta_in.chapters:
                manga.chapters.append(
                    models.ChapterEntry(manga_volume_id=manga.id, **ch_in.model_dump())
                )
        log.info("MangaVolume item_id=%s: %s chapters written", item_id, len(meta_in.chapters))

    db.add(manga)
    await db.commit()
    return await get_manga_volume(db, item_id)
