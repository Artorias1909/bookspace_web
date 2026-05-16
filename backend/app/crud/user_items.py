import logging
from typing import List, Optional

from sqlalchemy import select, func, or_, asc, desc, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, contains_eager

from .. import models, schemas

log = logging.getLogger("bookspace.crud")

# Eager-load options for UserItemData → Item (with manga_meta+chapters, series, box_set)
_ENTRY_LOAD = (
    selectinload(models.UserItemData.item)
    .selectinload(models.Item.manga_meta)
    .selectinload(models.MangaVolume.chapters),
    selectinload(models.UserItemData.item)
    .selectinload(models.Item.series),
    selectinload(models.UserItemData.item)
    .selectinload(models.Item.box_set),
)


def calculate_progress(current_page: int, total_pages: Optional[int]) -> float:
    """Return reading progress as a percentage [0.0, 100.0]."""
    if not total_pages or total_pages <= 0:
        return 0.0
    return round(min(current_page / total_pages * 100.0, 100.0), 2)


async def create_user_item_data(
    db: AsyncSession,
    user_id: int,
    user_item_data_in: schemas.UserItemDataCreate,
) -> models.UserItemData:
    from .items import create_item, get_item

    if user_item_data_in.item_id:
        log.debug("create_user_item_data: reusing existing item id=%s", user_item_data_in.item_id)
        item = await get_item(db, user_item_data_in.item_id)
        if item is None:
            log.error("create_user_item_data: item id=%s not found", user_item_data_in.item_id)
            raise ValueError(f"Item {user_item_data_in.item_id} not found")
    elif user_item_data_in.item:
        log.debug("create_user_item_data: creating new item '%s'", user_item_data_in.item.title)
        item = await create_item(db, user_item_data_in.item)
    else:
        log.error("create_user_item_data: neither item_id nor item provided")
        raise ValueError("Item data is required")

    existing = await get_user_item_by_item_id(db, user_id, item.id)
    if existing:
        log.debug("create_user_item_data: item_id=%s already in library for user_id=%s", item.id, user_id)
        raise ValueError("already_in_library")

    current_page = user_item_data_in.current_page or 0
    progress_percent = calculate_progress(current_page, item.page_count)
    entry = models.UserItemData(
        user_id=user_id,
        item_id=item.id,
        status=user_item_data_in.status or "unread",
        current_page=current_page,
        progress_percent=progress_percent,
    )
    db.add(entry)
    await db.commit()

    result = await db.execute(
        select(models.UserItemData).options(*_ENTRY_LOAD).where(models.UserItemData.id == entry.id)
    )
    entry = result.scalars().first()
    log.info(
        "UserItemData created: user_id=%s item_id=%s status=%s progress=%.1f%%",
        user_id, item.id, entry.status, progress_percent,
    )
    return entry


async def get_user_item_by_item_id(
    db: AsyncSession, user_id: int, item_id: int
) -> Optional[models.UserItemData]:
    result = await db.execute(
        select(models.UserItemData)
        .options(*_ENTRY_LOAD)
        .where(
            models.UserItemData.user_id == user_id,
            models.UserItemData.item_id == item_id,
        )
    )
    return result.scalars().first()


async def user_owns_series(db: AsyncSession, user_id: int, series_id: int) -> bool:
    """Return True if the user has at least one item from this series in their library."""
    result = await db.execute(
        select(models.UserItemData.id)
        .join(models.Item, models.UserItemData.item_id == models.Item.id)
        .where(
            models.UserItemData.user_id == user_id,
            models.Item.series_id == series_id,
        )
        .limit(1)
    )
    return result.scalars().first() is not None


async def get_user_item(
    db: AsyncSession, entry_id: int, user_id: int
) -> Optional[models.UserItemData]:
    result = await db.execute(
        select(models.UserItemData)
        .options(*_ENTRY_LOAD)
        .where(
            models.UserItemData.id == entry_id,
            models.UserItemData.user_id == user_id,
        )
    )
    entry = result.scalars().first()
    if not entry:
        log.debug("UserItemData id=%s not found for user_id=%s", entry_id, user_id)
    return entry


def _user_items_base_query(
    user_id: int,
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    """Build the base query for listing/counting a user's library entries."""
    query = (
        select(models.UserItemData)
        .join(models.UserItemData.item)
        .options(
            contains_eager(models.UserItemData.item)
            .selectinload(models.Item.manga_meta)
            .selectinload(models.MangaVolume.chapters),
            contains_eager(models.UserItemData.item).selectinload(models.Item.series),
            contains_eager(models.UserItemData.item).selectinload(models.Item.box_set),
        )
        .where(models.UserItemData.user_id == user_id)
    )
    if status:
        query = query.where(models.UserItemData.status == status)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                models.Item.title.ilike(pattern),
                func.cast(models.Item.authors, String).ilike(pattern),
                models.Item.genre.ilike(pattern),
                models.Item.volume_title.ilike(pattern),
            )
        )
    return query


async def count_user_items(
    db: AsyncSession,
    user_id: int,
    q: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    subq = _user_items_base_query(user_id, q, status).subquery()
    result = await db.execute(select(func.count()).select_from(subq))
    return result.scalar_one()


async def list_user_items(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 24,
    sort_by: str = "title",
    sort_dir: str = "asc",
    q: Optional[str] = None,
    status: Optional[str] = None,
) -> List[models.UserItemData]:
    _SORT_COLUMNS = {
        "title": models.Item.title,
        "author": models.Item.authors,
        "publication_year": models.Item.publication_year,
        "status": models.UserItemData.status,
    }
    order_col = _SORT_COLUMNS.get(sort_by, models.Item.title)
    order_fn = asc if sort_dir == "asc" else desc

    query = (
        _user_items_base_query(user_id, q, status)
        .order_by(order_fn(order_col))
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    result = await db.execute(query)
    rows = result.scalars().unique().all()
    log.debug("list_user_items user_id=%s q=%r page=%s → %s rows", user_id, q, page, len(rows))
    return rows


async def update_user_item_data(
    db: AsyncSession,
    entry: models.UserItemData,
    update_in: schemas.UserItemDataUpdate,
) -> models.UserItemData:
    entry_id, user_id = entry.id, entry.user_id
    if update_in.status is not None:
        entry.status = update_in.status
    if update_in.current_page is not None:
        entry.current_page = max(0, update_in.current_page)
    entry.progress_percent = calculate_progress(entry.current_page, entry.item.page_count)
    db.add(entry)
    await db.commit()
    log.info(
        "UserItemData id=%s updated: status=%s page=%s",
        entry_id, update_in.status, update_in.current_page,
    )
    return await get_user_item(db, entry_id, user_id)


async def delete_user_item(db: AsyncSession, entry: models.UserItemData) -> None:
    await db.delete(entry)
    await db.commit()
    log.info("UserItemData id=%s deleted (user_id=%s)", entry.id, entry.user_id)
