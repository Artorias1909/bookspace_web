import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import select, func, or_, asc, desc, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, contains_eager

from . import models, schemas, auth

log_crud = logging.getLogger("bookspace.crud")
log_isbn = logging.getLogger("bookspace.isbn")

GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
SEARCH_FIELDS = [models.Item.title, models.Item.genre, models.Item.language]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.username == username))
    return result.scalars().first()


async def create_user(db: AsyncSession, user_in: schemas.UserCreate) -> models.User:
    hashed_password = auth.get_password_hash(user_in.password)
    user = models.User(username=user_in.username, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log_crud.info("User created: '%s' (id=%s)", user.username, user.id)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[models.User]:
    user = await get_user_by_username(db, username)
    if not user:
        log_crud.warning("Login failed — unknown user '%s'", username)
        return None
    if not auth.verify_password(password, user.hashed_password):
        log_crud.warning("Login failed — wrong password for user '%s'", username)
        return None
    log_crud.info("User '%s' authenticated successfully", username)
    return user


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------

async def create_series(db: AsyncSession, series_in: schemas.SeriesCreate) -> models.Series:
    series = models.Series(**series_in.model_dump())
    db.add(series)
    await db.commit()
    await db.refresh(series)
    log_crud.info("Series created: '%s' (id=%s, type=%s)", series.name, series.id, series.type)
    return series


async def get_series(db: AsyncSession, series_id: int) -> Optional[models.Series]:
    result = await db.execute(select(models.Series).where(models.Series.id == series_id))
    series = result.scalars().first()
    if not series:
        log_crud.debug("Series id=%s not found", series_id)
    return series


async def list_series(db: AsyncSession, limit: int = 50, offset: int = 0) -> List[models.Series]:
    result = await db.execute(select(models.Series).limit(limit).offset(offset))
    rows = result.scalars().all()
    log_crud.debug("list_series → %s rows", len(rows))
    return rows


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

async def create_item(db: AsyncSession, item_in: schemas.ItemCreate) -> models.Item:
    data = item_in.model_dump(exclude_none=True)
    item = models.Item(**data)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    item_id = item.id
    log_crud.info("Item created: '%s' (id=%s)", item.title, item_id)
    return await get_item(db, item_id)


async def get_item(db: AsyncSession, item_id: int) -> Optional[models.Item]:
    result = await db.execute(
        select(models.Item)
        .options(
            selectinload(models.Item.series),
            selectinload(models.Item.manga_meta).selectinload(models.MangaVolume.chapters),
        )
        .where(models.Item.id == item_id)
    )
    item = result.scalars().first()
    if not item:
        log_crud.debug("Item id=%s not found", item_id)
    return item


async def search_items(
    db: AsyncSession, q: str, limit: int = 25, offset: int = 0
) -> List[models.Item]:
    result = await db.execute(
        select(models.Item)
        .options(
            selectinload(models.Item.series),
            selectinload(models.Item.manga_meta).selectinload(models.MangaVolume.chapters),
        )
        .where(models.Item.title.ilike(f"%{q}%"))
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    log_crud.debug("search_items q=%r → %s results", q, len(rows))
    return rows


async def update_item(db: AsyncSession, item: models.Item, item_update: schemas.ItemUpdate) -> models.Item:
    changes = item_update.model_dump(exclude_unset=True)
    item_id = item.id
    for key, value in changes.items():
        setattr(item, key, value)
    db.add(item)
    await db.commit()
    log_crud.info("Item id=%s updated: fields=%s", item_id, list(changes.keys()))
    return await get_item(db, item_id)


async def assign_item_to_series(
    db: AsyncSession,
    item_id: int,
    series_id: int,
    volume_number: Optional[str] = None,
) -> Optional[models.Item]:
    item = await get_item(db, item_id)
    if not item:
        log_crud.warning("assign_item_to_series: item id=%s not found", item_id)
        return None
    item.series_id = series_id
    if volume_number is not None:
        item.volume_number = volume_number
    db.add(item)
    await db.commit()
    log_crud.info("Item id=%s assigned to series id=%s (vol=%s)", item_id, series_id, volume_number)
    return await get_item(db, item_id)


async def list_series_items(db: AsyncSession, series_id: int) -> List[models.Item]:
    result = await db.execute(
        select(models.Item)
        .options(
            selectinload(models.Item.series),
            selectinload(models.Item.manga_meta).selectinload(models.MangaVolume.chapters),
        )
        .where(models.Item.series_id == series_id)
        .order_by(models.Item.volume_number.asc().nullsfirst(), models.Item.title.asc())
    )
    rows = result.scalars().all()
    log_crud.debug("list_series_items series_id=%s → %s items", series_id, len(rows))
    return rows


# ---------------------------------------------------------------------------
# User item data
# ---------------------------------------------------------------------------

async def create_user_item_data(
    db: AsyncSession,
    user_id: int,
    user_item_data_in: schemas.UserItemDataCreate,
) -> models.UserItemData:
    item = None
    if user_item_data_in.item_id:
        log_crud.debug("create_user_item_data: reusing existing item id=%s", user_item_data_in.item_id)
        item = await get_item(db, user_item_data_in.item_id)
        if item is None:
            log_crud.error("create_user_item_data: item id=%s not found", user_item_data_in.item_id)
            raise ValueError(f"Item {user_item_data_in.item_id} not found")
    elif user_item_data_in.item:
        log_crud.debug("create_user_item_data: creating new item '%s'", user_item_data_in.item.title)
        item = await create_item(db, user_item_data_in.item)
    else:
        log_crud.error("create_user_item_data: neither item_id nor item provided")
        raise ValueError("Item data is required")

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
        select(models.UserItemData)
        .options(
            selectinload(models.UserItemData.item)
            .selectinload(models.Item.manga_meta)
            .selectinload(models.MangaVolume.chapters)
        )
        .where(models.UserItemData.id == entry.id)
    )
    entry = result.scalars().first()
    log_crud.info(
        "UserItemData created: user_id=%s item_id=%s status=%s progress=%.1f%%",
        user_id, item.id, entry.status, progress_percent,
    )
    return entry


async def get_user_item(db: AsyncSession, entry_id: int, user_id: int) -> Optional[models.UserItemData]:
    result = await db.execute(
        select(models.UserItemData)
        .options(
            selectinload(models.UserItemData.item)
            .selectinload(models.Item.manga_meta)
            .selectinload(models.MangaVolume.chapters)
        )
        .where(
            models.UserItemData.id == entry_id,
            models.UserItemData.user_id == user_id,
        )
    )
    entry = result.scalars().first()
    if not entry:
        log_crud.debug("UserItemData id=%s not found for user_id=%s", entry_id, user_id)
    return entry


def _user_items_base_query(
    user_id: int,
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    query = (
        select(models.UserItemData)
        .join(models.UserItemData.item)
        .options(
            contains_eager(models.UserItemData.item).selectinload(models.Item.manga_meta),
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
    query = _user_items_base_query(user_id, q, status)
    order_column = models.Item.title
    if sort_by == "author":
        order_column = models.Item.authors
    elif sort_by == "publication_year":
        order_column = models.Item.publication_year
    elif sort_by == "status":
        order_column = models.UserItemData.status
    query = query.order_by(asc(order_column) if sort_dir == "asc" else desc(order_column))
    query = query.limit(page_size).offset((page - 1) * page_size)
    result = await db.execute(query)
    rows = result.scalars().unique().all()
    log_crud.debug(
        "list_user_items user_id=%s q=%r page=%s → %s rows", user_id, q, page, len(rows)
    )
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
    log_crud.info(
        "UserItemData id=%s updated: status=%s page=%s",
        entry_id, update_in.status, update_in.current_page,
    )
    return await get_user_item(db, entry_id, user_id)


# ---------------------------------------------------------------------------
# ISBN lookup
# ---------------------------------------------------------------------------

async def parse_isbn_metadata(isbn: str) -> Tuple[Dict[str, Any], str]:
    sanitized = re.sub(r"[^0-9Xx]", "", isbn)
    if not sanitized:
        raise ValueError("Invalid ISBN: no digits found.")
    if len(sanitized) not in (10, 13):
        raise ValueError(f"Invalid ISBN length ({len(sanitized)} digits). Expected 10 or 13.")

    log_isbn.info("ISBN lookup started — raw=%r sanitized=%r", isbn, sanitized)

    headers = {"User-Agent": "Bookspace/1.0 (personal library tracker)"}
    google_rate_limited = False
    google_error: Optional[str] = None
    ol_error: Optional[str] = None

    try:
        async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as client:

            # ── Google Books ────────────────────────────────────────────────
            try:
                google_params: Dict[str, str] = {"q": f"isbn:{sanitized}"}
                if GOOGLE_BOOKS_API_KEY:
                    google_params["key"] = GOOGLE_BOOKS_API_KEY
                    log_isbn.debug("Google Books: querying with API key")
                else:
                    log_isbn.debug("Google Books: querying without API key (shared quota)")

                google_resp = await client.get(
                    "https://www.googleapis.com/books/v1/volumes",
                    params=google_params,
                )
                log_isbn.debug("Google Books: HTTP %s", google_resp.status_code)

                if google_resp.status_code == 200:
                    data = google_resp.json()
                    total = data.get("totalItems", 0)
                    log_isbn.debug("Google Books: totalItems=%s", total)
                    if total > 0:
                        book = parse_google_book(data["items"][0])
                        log_isbn.info(
                            "Google Books: found '%s' by %s",
                            book.get("title"), book.get("authors"),
                        )
                        return book, "google"
                    else:
                        log_isbn.warning("Google Books: no results for ISBN %s", sanitized)
                        google_error = "Google Books returned no results for this ISBN."

                elif google_resp.status_code == 429:
                    log_isbn.warning(
                        "Google Books: rate limited (429) — %s API key",
                        "with" if GOOGLE_BOOKS_API_KEY else "without",
                    )
                    google_rate_limited = True
                    google_error = (
                        "Google Books daily quota exceeded."
                        if not GOOGLE_BOOKS_API_KEY
                        else "Google Books API key quota exceeded."
                    )

                elif google_resp.status_code == 400:
                    body = google_resp.json()
                    msg = body.get("error", {}).get("message", "Bad request")
                    log_isbn.error("Google Books: 400 Bad Request — %s", msg)
                    google_error = f"Google Books rejected the request: {msg}"

                elif google_resp.status_code == 403:
                    log_isbn.error("Google Books: 403 Forbidden — API key invalid or Books API not enabled")
                    google_error = "Google Books API key is invalid or the Books API is not enabled in Google Cloud."

                else:
                    log_isbn.warning("Google Books: unexpected HTTP %s", google_resp.status_code)
                    google_error = f"Google Books returned HTTP {google_resp.status_code}."

            except httpx.TimeoutException:
                log_isbn.warning("Google Books: request timed out")
                google_error = "Google Books request timed out."
            except httpx.ConnectError as exc:
                log_isbn.warning("Google Books: connection error — %s", exc)
                google_error = "Could not connect to Google Books."
            except httpx.RequestError as exc:
                log_isbn.warning("Google Books: network error — %s", exc)
                google_error = f"Google Books network error: {exc}"

            # ── Open Library ────────────────────────────────────────────────
            try:
                log_isbn.debug("Open Library: querying /api/books for ISBN %s", sanitized)
                ol_resp = await client.get(
                    "https://openlibrary.org/api/books",
                    params={"bibkeys": f"ISBN:{sanitized}", "jscmd": "data", "format": "json"},
                )
                log_isbn.debug("Open Library: HTTP %s", ol_resp.status_code)

                if ol_resp.status_code == 200:
                    data = ol_resp.json()
                    key = f"ISBN:{sanitized}"
                    if key in data:
                        book = parse_open_library_api(data[key], sanitized)
                        log_isbn.info(
                            "Open Library: found '%s' by %s",
                            book.get("title"), book.get("authors"),
                        )
                        return book, "openlibrary"
                    else:
                        log_isbn.warning("Open Library: no entry for key '%s'", key)
                        ol_error = "Open Library has no record for this ISBN."
                else:
                    log_isbn.warning("Open Library: unexpected HTTP %s", ol_resp.status_code)
                    ol_error = f"Open Library returned HTTP {ol_resp.status_code}."

            except httpx.TimeoutException:
                log_isbn.warning("Open Library: request timed out")
                ol_error = "Open Library request timed out."
            except httpx.ConnectError as exc:
                log_isbn.warning("Open Library: connection error — %s", exc)
                ol_error = "Could not connect to Open Library."
            except httpx.RequestError as exc:
                log_isbn.warning("Open Library: network error — %s", exc)
                ol_error = f"Open Library network error: {exc}"

    except Exception as exc:
        log_isbn.error("ISBN lookup: unexpected error for %r — %s", sanitized, exc, exc_info=True)
        raise ValueError(f"Unexpected error during ISBN lookup: {exc}") from exc

    # ── All sources exhausted — build a clear error message ─────────────────
    log_isbn.error(
        "ISBN lookup failed for %s — Google: %s | OpenLibrary: %s",
        sanitized, google_error, ol_error,
    )

    parts: List[str] = []
    if google_rate_limited:
        if GOOGLE_BOOKS_API_KEY:
            parts.append("Google Books API key quota is exhausted — check your billing or wait for it to reset.")
        else:
            parts.append(
                "Google Books daily quota is exhausted (shared anonymous limit). "
                "Add a free GOOGLE_BOOKS_API_KEY to .env for a dedicated quota."
            )
    elif google_error:
        parts.append(f"Google Books: {google_error}")

    if ol_error:
        parts.append(f"Open Library: {ol_error}")

    if not parts:  # pragma: no cover
        parts.append("No metadata found for this ISBN.")

    parts.append("You can add the book manually using the manual entry tab.")
    raise ValueError(" | ".join(parts))


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_google_book(item: Dict[str, Any]) -> Dict[str, Any]:
    info = item.get("volumeInfo", {})
    title = info.get("title", "")
    authors = info.get("authors", [])

    pub_date = info.get("publishedDate", "")
    try:
        pub_year = int(pub_date[:4]) if pub_date else None
    except (ValueError, TypeError):
        pub_year = None

    cats = info.get("categories", [])
    img = info.get("imageLinks", {})

    return {
        "title": title,
        "authors": authors,
        "publication_year": pub_year,
        "genre": ", ".join(cats[:3]) if cats else None,
        "page_count": info.get("pageCount"),
        "description": info.get("description"),
        "isbn": get_isbn_from_info(info),
        "cover_url": img.get("large") or img.get("thumbnail") or img.get("smallThumbnail"),
        "language": info.get("language"),
        **extract_series_fields(title, info.get("subtitle", "")),
    }


def parse_open_library_api(data: Dict[str, Any], isbn_fallback: str = "") -> Dict[str, Any]:
    title = data.get("title", "")
    authors = [
        a["name"] for a in data.get("authors", [])
        if isinstance(a, dict) and a.get("name")
    ]

    pub_date = data.get("publish_date", "")
    try:
        pub_year = int(str(pub_date)[:4]) if pub_date else None
    except (ValueError, TypeError):
        pub_year = None

    identifiers = data.get("identifiers", {})
    isbn = (
        (identifiers.get("isbn_13") or [None])[0]
        or (identifiers.get("isbn_10") or [None])[0]
        or isbn_fallback
    )

    cover = data.get("cover", {})
    cover_url = cover.get("large") or cover.get("medium") or cover.get("small")

    subjects = [
        s["name"] for s in data.get("subjects", [])
        if isinstance(s, dict) and s.get("name")
    ]

    return {
        "title": title,
        "authors": authors,
        "publication_year": pub_year,
        "genre": ", ".join(subjects[:3]) if subjects else None,
        "page_count": data.get("number_of_pages"),
        "description": (
            data.get("excerpts", [{}])[0].get("text")
            if data.get("excerpts") else None
        ),
        "isbn": isbn,
        "cover_url": cover_url,
        "language": None,
        **extract_series_fields(title, None),
    }


def parse_open_library(data: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy parser for Open Library /isbn/{isbn}.json responses."""
    title = data.get("title", "")
    authors = [
        a["name"] for a in data.get("authors", [])
        if isinstance(a, dict) and a.get("name")
    ]
    pub_date = data.get("publish_date", "")
    try:
        pub_year = int(str(pub_date)[:4]) if pub_date else None
    except (ValueError, TypeError):
        pub_year = None

    return {
        "title": title,
        "authors": authors,
        "publication_year": pub_year,
        "genre": None,
        "page_count": data.get("number_of_pages"),
        "description": data.get("notes") if isinstance(data.get("notes"), str) else None,
        "isbn": (data.get("isbn_13") or [None])[0] or (data.get("isbn_10") or [None])[0],
        "cover_url": (
            f"https://covers.openlibrary.org/b/id/{data['covers'][0]}-L.jpg"
            if data.get("covers") else None
        ),
        "language": (
            data["languages"][0].get("key", "").split("/")[-1]
            if data.get("languages") else None
        ),
        **extract_series_fields(title, None),
    }


def get_isbn_from_info(volume_info: Dict[str, Any]) -> Optional[str]:
    for identifier in volume_info.get("industryIdentifiers", []):
        if identifier.get("type") in ("ISBN_13", "ISBN_10"):
            return identifier.get("identifier")
    return None


SERIES_PATTERNS = [
    r"(?P<series>.+?)\s+Vol(?:ume)?\.?\s*(?P<volume>\d+)",
    r"(?P<series>.+?)\s+Band\s*(?P<volume>\d+)",
    r"(?P<series>.+?)\s+#(?P<volume>\d+)",
]


def extract_series_fields(title: str, subtitle: Optional[str]) -> Dict[str, Any]:
    text = " ".join(filter(None, [title, subtitle]))
    for pattern in SERIES_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                "series_id": None,
                "volume_number": match.group("volume"),
                "volume_title": title,
            }
    return {"series_id": None, "volume_number": None, "volume_title": None}


def calculate_progress(current_page: int, total_pages: Optional[int]) -> float:
    if not total_pages or total_pages <= 0:
        return 0.0
    return round(min(current_page / total_pages * 100.0, 100.0), 2)


# ---------------------------------------------------------------------------
# Manga metadata
# ---------------------------------------------------------------------------

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

    is_new = existing is None
    if existing:
        # Update scalar fields
        for field in ("original_title", "romanized_title", "demographic", "reading_direction", "dnb_id", "animexx_id"):
            val = getattr(meta_in, field, None)
            if val is not None:
                setattr(existing, field, val)
        manga = existing
        log_crud.info("MangaVolume updated for item_id=%s", item_id)
    else:
        manga = models.MangaVolume(
            item_id=item_id,
            original_title=meta_in.original_title,
            romanized_title=meta_in.romanized_title,
            demographic=meta_in.demographic,
            reading_direction=meta_in.reading_direction,
            dnb_id=meta_in.dnb_id,
            animexx_id=meta_in.animexx_id,
        )
        db.add(manga)
        await db.flush()  # get manga.id before inserting chapters
        log_crud.info("MangaVolume created for item_id=%s", item_id)

    # Replace chapter list when provided
    if meta_in.chapters is not None:
        if is_new:
            # New manga: collection is unloaded — add directly to the session
            # (avoids triggering an implicit load on an async session).
            for ch_in in meta_in.chapters:
                db.add(models.ChapterEntry(manga_volume_id=manga.id, **ch_in.model_dump()))
        else:
            # Existing manga: collection is already loaded by get_manga_volume above.
            # Clear via the collection so delete-orphan cascade fires and the
            # in-memory state stays consistent across the identity map.
            manga.chapters.clear()
            for ch_in in meta_in.chapters:
                manga.chapters.append(
                    models.ChapterEntry(manga_volume_id=manga.id, **ch_in.model_dump())
                )
        log_crud.info("MangaVolume item_id=%s: %s chapters written", item_id, len(meta_in.chapters))

    db.add(manga)
    await db.commit()
    return await get_manga_volume(db, item_id)
