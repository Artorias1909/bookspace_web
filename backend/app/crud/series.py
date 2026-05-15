import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas

log = logging.getLogger("bookspace.crud")


async def create_series(db: AsyncSession, series_in: schemas.SeriesCreate) -> models.Series:
    series = models.Series(**series_in.model_dump())
    db.add(series)
    await db.commit()
    await db.refresh(series)
    log.info("Series created: '%s' (id=%s, type=%s)", series.name, series.id, series.type)
    return series


async def get_series(db: AsyncSession, series_id: int) -> Optional[models.Series]:
    result = await db.execute(select(models.Series).where(models.Series.id == series_id))
    series = result.scalars().first()
    if not series:
        log.debug("Series id=%s not found", series_id)
    return series


async def list_series(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> List[models.Series]:
    result = await db.execute(select(models.Series).limit(limit).offset(offset))
    rows = result.scalars().all()
    log.debug("list_series → %s rows", len(rows))
    return rows
