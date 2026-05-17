"""Series CRUD: creation, lookup, bulk status updates, and library deletion."""
import logging
from typing import List, Optional

from sqlalchemy import select, func, delete as sa_delete, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas

log = logging.getLogger("bookspace.crud")


async def create_series(db: AsyncSession, series_in: schemas.SeriesCreate) -> models.Series:
    """Persist a new Series row and return the refreshed instance."""
    series = models.Series(**series_in.model_dump())
    db.add(series)
    await db.commit()
    await db.refresh(series)
    log.info("Series created: '%s' (id=%s, type=%s)", series.name, series.id, series.type)
    return series


async def get_series(db: AsyncSession, series_id: int) -> Optional[models.Series]:
    """Fetch a Series by primary key, or None if not found."""
    result = await db.execute(select(models.Series).where(models.Series.id == series_id))
    series = result.scalars().first()
    if not series:
        log.debug("Series id=%s not found", series_id)
    return series


async def find_or_create_series(
    db: AsyncSession,
    name: str,
    media_type: str,
) -> models.Series:
    """Return an existing series matching name+type (case-insensitive, ignoring underscores), or create it."""
    normalized = name.replace("_", " ").strip()
    result = await db.execute(
        select(models.Series).where(
            func.lower(func.replace(models.Series.name, "_", " ")) == normalized.lower(),
            models.Series.type == media_type,
        )
    )
    existing = result.scalars().first()
    if existing:
        log.debug("find_or_create_series: found existing '%s' (id=%s)", normalized, existing.id)
        return existing
    new_series = await create_series(db, schemas.SeriesCreate(name=normalized, type=media_type))
    log.info("find_or_create_series: created '%s' (id=%s, type=%s)", normalized, new_series.id, media_type)
    return new_series


async def find_series_by_name(db: AsyncSession, name: str) -> Optional[models.Series]:
    """Find any series matching name (case-insensitive, any media type).

    Prefers manga > comic > book so that boxsets link to the canonical manga series.
    """
    normalized = name.lower().replace("_", " ").strip()
    result = await db.execute(
        select(models.Series).where(
            func.lower(func.replace(models.Series.name, "_", " ")) == normalized
        )
    )
    rows = result.scalars().all()
    for preferred in ("manga", "comic", "book"):
        for s in rows:
            if s.type == preferred:
                return s
    return rows[0] if rows else None


async def list_series(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> List[models.Series]:
    """Return up to `limit` Series rows starting at `offset`."""
    result = await db.execute(select(models.Series).limit(limit).offset(offset))
    rows = result.scalars().all()
    log.debug("list_series → %s rows", len(rows))
    return rows


async def delete_user_series_entries(
    db: AsyncSession,
    user_id: int,
    series_id: int,
) -> int:
    """Delete all of a user's library entries for every item in a series.

    Returns the number of deleted entries.
    """
    item_ids_sq = select(models.Item.id).where(models.Item.series_id == series_id)
    stmt = (
        sa_delete(models.UserItemData)
        .where(
            models.UserItemData.user_id == user_id,
            models.UserItemData.item_id.in_(item_ids_sq),
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    count = result.rowcount
    log.info("delete_user_series_entries: series_id=%s user_id=%s deleted=%s", series_id, user_id, count)
    return count


async def bulk_update_series_status(
    db: AsyncSession,
    user_id: int,
    series_id: int,
    status: str,
) -> int:
    """Set all of a user's library entries for every item in a series to status.

    When status is 'completed', also sets current_page = page_count and progress_percent = 100.0.
    Returns the number of updated entries.
    """
    item_ids_sq = select(models.Item.id).where(models.Item.series_id == series_id)

    if status != "completed":
        stmt = (
            sa_update(models.UserItemData)
            .where(
                models.UserItemData.user_id == user_id,
                models.UserItemData.item_id.in_(item_ids_sq),
            )
            .values(status=status)
        )
        result = await db.execute(stmt)
        await db.commit()
        count = result.rowcount
    else:
        # "completed" requires per-item current_page from page_count
        result = await db.execute(
            select(models.UserItemData)
            .join(models.Item, models.UserItemData.item_id == models.Item.id)
            .options(selectinload(models.UserItemData.item))
            .where(
                models.UserItemData.user_id == user_id,
                models.Item.series_id == series_id,
            )
        )
        entries = result.scalars().all()
        for entry in entries:
            entry.status = "completed"
            if entry.item.page_count:
                entry.current_page = entry.item.page_count
        await db.commit()
        count = len(entries)

    log.info("bulk_update_series_status: series_id=%s user_id=%s status=%s updated=%s", series_id, user_id, status, count)
    return count
