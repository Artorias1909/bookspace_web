"""ISBN import router: multi-source metadata lookup and automatic item/series/boxset creation."""
import asyncio
import logging
import unicodedata
from typing import Union

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import anilist, crud, dnb, mangapassion, models, schemas
from ..crud.isbn import detect_boxset, extract_boxset_series_name
from ..crud.items import _ITEM_LOAD
from ..deps import get_db_session
from ..auth import get_current_user

log = logging.getLogger("bookspace.isbn")
router = APIRouter()


@router.post("/isbn", response_model=None, status_code=201)
async def import_by_isbn(
    import_in: schemas.ISBNImportRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
) -> Union[schemas.ISBNImportResponse, schemas.BoxSetImportResponse]:
    """Import a book or manga by ISBN.

    Lookup pipeline:
      1. DNB (Deutsche Nationalbibliothek) — best for German manga: series title,
         volume number (normalised), chapters, demographic, original title.
      2. Google Books / Open Library — queried in parallel with DNB.
      3. Merge: DNB wins for structured fields; Google/OL fills cover and gaps.
      4. AniList — queried for manga titles to enrich with high-res cover and
         Japanese original title when the result is identified as a manga.
      5. Manga-Passion — queried for manga titles to enrich with official German
         publisher (Carlsen) cover, canonical series name, and German volume title.

    Post-import actions (all non-fatal):
      - MangaVolume row created automatically for manga items.
      - Series record found-or-created; item linked with normalised volume number.
      - If ISBN is a collector box (Sammelschuber), returns BoxSetImportResponse
        with all individual volumes pre-created.
    """
    isbn = "".join(c for c in import_in.isbn if unicodedata.category(c) not in ("Cf", "Zs")).strip()
    if not isbn:
        raise HTTPException(status_code=400, detail="ISBN must not be empty.")

    log.info("ISBN import: '%s' (user=%s)", isbn, current_user.id)

    # ── 0a: Return existing item if already imported ─────────────────────────
    existing = await crud.get_item_by_isbn(db, isbn)
    if existing:
        log.info("ISBN '%s' already in DB (item_id=%s), returning cached", isbn, existing.id)
        item_data = schemas.ItemRead.model_validate(existing)
        in_lib = await crud.get_user_item_by_item_id(db, current_user.id, existing.id)
        return schemas.ISBNImportResponse(
            **item_data.model_dump(), source="cache", raw_metadata=None,
            already_in_library=bool(in_lib),
        )

    # ── 0b: Return existing boxset if already imported ───────────────────────
    existing_box = await crud.get_box_set_by_isbn(db, isbn)
    if existing_box:
        log.info("ISBN '%s' already in DB as BoxSet (id=%s), returning cached", isbn, existing_box.id)
        return await _build_boxset_response(db, existing_box, source="cache", user_id=current_user.id)

    # ── 1 + 2: DNB and Google/OL in parallel ────────────────────────────────
    try:
        dnb_result, (google_ol_result, google_ol_source) = await asyncio.gather(
            dnb.fetch_dnb_by_isbn(isbn),
            _fetch_google_or_ol(isbn),
        )
        metadata, source = _merge_metadata(dnb_result, google_ol_result, google_ol_source)
    except ValueError as exc:
        log.warning("ISBN lookup exhausted for '%s': %s", isbn, exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except httpx.RequestError as exc:
        log.error("Network error during ISBN lookup for '%s': %s", isbn, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Could not reach metadata service: {exc}")
    except Exception as exc:
        log.error("Unexpected error during ISBN import for '%s': %s", isbn, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.")

    log.info("ISBN '%s' resolved via %s: '%s'", isbn, source, metadata.get("title", "(no title)"))

    # ── 2b: Detect Sammelbox / collector box ────────────────────────────────
    title = metadata.get("title", "")
    boxset_info = detect_boxset(title)
    if boxset_info is not None:
        arc_name, vol_from, vol_to = boxset_info
        log.info("Detected boxset '%s': arc=%r vol %s-%s", title, arc_name, vol_from, vol_to)
        return await _handle_boxset_import(db, isbn, metadata, source, arc_name, vol_from, vol_to, current_user.id)

    # ── 3: AniList enrichment for manga ─────────────────────────────────────
    if metadata.get("media_type") == "manga":
        search_title = metadata.get("series_name") or metadata.get("title", "")
        anilist_data = await anilist.fetch_anilist_by_title(search_title)
        if anilist_data:
            _apply_anilist(metadata, anilist_data)

    # ── 4: Manga-Passion enrichment for manga ────────────────────────────────
    if metadata.get("media_type") == "manga":
        mp_series = metadata.get("series_name") or metadata.get("title", "")
        mp_vol_raw = metadata.get("volume_number")
        try:
            mp_vol_int = int(float(mp_vol_raw)) if mp_vol_raw is not None else None
        except (ValueError, TypeError):
            mp_vol_int = None
        mp_data = await mangapassion.fetch_manga_metadata(
            mp_series, mp_vol_int, volume_title=metadata.get("volume_title"),
        )
        if mp_data:
            _apply_mangapassion(metadata, mp_data)

    # ── 5: Persist Item ─────────────────────────────────────────────────────
    try:
        item_in = schemas.ItemCreate(
            **{k: v for k, v in metadata.items() if k in schemas.ItemCreate.model_fields}
        )
        item = await crud.create_item(db, item_in)
    except SQLAlchemyError:
        log.error("Database error saving ISBN import for '%s'", isbn, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Metadata found but could not be saved. Please try again.",
        )

    # ── 6: Auto-create MangaVolume ───────────────────────────────────────────
    if item.media_type == "manga":
        try:
            manga_in = schemas.MangaVolumeCreate(
                original_title=metadata.get("original_title"),
                romanized_title=metadata.get("romanized_title"),
                demographic=metadata.get("demographic"),
                dnb_id=metadata.get("dnb_id"),
                chapters=[
                    schemas.ChapterEntryCreate(**ch)
                    for ch in metadata.get("chapters", [])
                ],
            )
            await crud.upsert_manga_volume(db, item.id, manga_in)
            log.info("MangaVolume created for item_id=%s (%s chapters)", item.id, len(manga_in.chapters))
        except SQLAlchemyError:
            log.error("Could not save MangaVolume for item_id=%s", item.id, exc_info=True)
            # Non-fatal: Item was saved; manga metadata can be added later

    # ── 7: Auto-link Series ──────────────────────────────────────────────────
    series_name = metadata.get("series_name")
    if series_name:
        try:
            series = await crud.find_or_create_series(db, series_name, item.media_type)
            volume_number = metadata.get("volume_number")
            await crud.assign_item_to_series(
                db, item.id, series.id,
                str(volume_number) if volume_number is not None else None,
            )
            log.info(
                "Item id=%s linked to series '%s' (id=%s) vol=%s",
                item.id, series_name, series.id, volume_number,
            )
        except SQLAlchemyError:
            log.error(
                "Could not auto-link series '%s' for item_id=%s",
                series_name, item.id, exc_info=True,
            )
            # Non-fatal

    # ── 8: Reload and return ─────────────────────────────────────────────────
    item_id_val = item.id
    db.expire(item)
    item = await crud.get_item(db, item_id_val)
    item_data = schemas.ItemRead.model_validate(item)
    in_lib = await crud.get_user_item_by_item_id(db, current_user.id, item_id_val)
    return schemas.ISBNImportResponse(
        **item_data.model_dump(), source=source, raw_metadata=metadata,
        already_in_library=bool(in_lib),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_google_or_ol(isbn: str):
    """Thin wrapper so we can gather() it alongside DNB."""
    try:
        return await crud.parse_isbn_metadata(isbn)
    except ValueError:
        return None, "none"


def _merge_metadata(
    dnb_data: dict | None,
    google_ol_data: dict | None,
    google_ol_source: str,
) -> tuple[dict, str]:
    """Merge DNB and Google/OL results into one dict.

    Priority:
    - DNB wins for structured fields (series, volume, chapters, demographic, …).
    - Google/OL wins for cover_url (DNB has none); fills any field DNB left None.
    - AniList cover is applied separately after this merge (see _apply_anilist).
    """
    if dnb_data and google_ol_data:
        merged = dict(google_ol_data)
        dnb_preferred = (
            "media_type", "series_name", "volume_number", "volume_title",
            "page_count", "description", "original_title", "romanized_title",
            "demographic", "dnb_id", "chapters", "language", "authors",
        )
        for key in dnb_preferred:
            if dnb_data.get(key) is not None:
                merged[key] = dnb_data[key]
        if dnb_data.get("title"):
            merged["title"] = dnb_data["title"]
        if dnb_data.get("publication_year"):
            merged["publication_year"] = dnb_data["publication_year"]
        return merged, f"dnb+{google_ol_source}"

    if dnb_data:
        return dict(dnb_data), "dnb"
    if google_ol_data:
        return dict(google_ol_data), google_ol_source

    raise ValueError(
        "No metadata found for this ISBN in any source (DNB, Google Books, Open Library). "
        "You can add the item manually."
    )


def _apply_anilist(metadata: dict, anilist_data: dict) -> None:
    """Merge AniList data into the metadata dict in-place.

    AniList takes priority for cover_url (high-res artwork beats thumbnails).
    For all other fields it only fills gaps left by DNB/Google.
    """
    # Cover: AniList always wins for manga (better quality than Google thumbnails)
    if anilist_data.get("cover_url"):
        metadata["cover_url"] = anilist_data["cover_url"]

    # Fill remaining gaps only
    for field in ("original_title", "romanized_title", "publication_year"):
        if not metadata.get(field) and anilist_data.get(field):
            metadata[field] = anilist_data[field]


async def _handle_boxset_import(
    db: AsyncSession,
    isbn: str,
    metadata: dict,
    source: str,
    arc_name: str | None,
    vol_from: int,
    vol_to: int,
    user_id: int | None = None,
) -> schemas.BoxSetImportResponse:
    """Create (or reuse) a BoxSet and its individual volume Items."""
    title = metadata.get("title", "")
    series_name = extract_boxset_series_name(title) or metadata.get("series_name") or title
    media_type = metadata.get("media_type") or "manga"
    authors = metadata.get("authors") or []
    cover_url = metadata.get("cover_url")
    publication_year = metadata.get("publication_year")

    try:
        # Find or create the canonical series (prefer existing manga series)
        series = await crud.find_series_by_name(db, series_name)
        if series is None:
            series = await crud.find_or_create_series(db, series_name, media_type)

        box = await crud.create_box_set(
            db,
            series_id=series.id,
            name=arc_name or title,
            isbn=isbn,
            volume_from=vol_from,
            volume_to=vol_to,
            cover_url=cover_url,
            publication_year=publication_year,
        )

        volume_items = []
        for vol_num in range(vol_from, vol_to + 1):
            item = await crud.find_or_create_volume_item(
                db,
                series_id=series.id,
                series_name=series.name,
                volume_number=vol_num,
                media_type=media_type,
                authors=authors,
                publication_year=publication_year,
                box_set_id=box.id,
            )
            volume_items.append(item)

        log.info(
            "BoxSet created: isbn=%s series='%s' arc=%r vol %s-%s (%s volumes)",
            isbn, series.name, arc_name, vol_from, vol_to, len(volume_items),
        )
        # Enrich each placeholder volume with full metadata (non-fatal)
        try:
            volume_items = await _enrich_boxset_volumes(db, series.name, media_type, volume_items)
        except Exception:
            log.warning("Could not enrich boxset volumes for '%s'", series.name, exc_info=True)
    except SQLAlchemyError:
        log.error("Database error saving boxset for isbn=%s", isbn, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Metadata found but could not be saved. Please try again.",
        )

    return await _build_boxset_response(db, box, source=source, volume_items=volume_items, user_id=user_id)


async def _enrich_boxset_volumes(
    db: AsyncSession,
    series_name: str,
    media_type: str,
    volume_items: list,
) -> list:
    """Enrich boxset placeholder items with full metadata from AniList + Manga-Passion.

    Fetches AniList once for the series cover, then Manga-Passion per volume in parallel.
    Non-fatal: returns original items if enrichment fails completely.
    """
    # Reload all items fresh — each find_or_create commit expires prior items in the
    # session, making attribute access raise MissingGreenlet on expired rows.
    item_ids = [i.id for i in volume_items]
    result = await db.execute(
        select(models.Item).options(*_ITEM_LOAD).where(models.Item.id.in_(item_ids))
    )
    id_to_item = {i.id: i for i in result.scalars().unique().all()}
    volume_items = [id_to_item[i.id] for i in volume_items if i.id in id_to_item]

    # AniList: one call for the whole series (cover + original title)
    anilist_data = None
    if media_type == "manga":
        try:
            anilist_data = await anilist.fetch_anilist_by_title(series_name)
        except Exception:
            log.debug("AniList lookup failed for series '%s'", series_name)

    # Manga-Passion: parallel calls, one per volume
    async def _fetch_mp(vol_num: int):
        try:
            return await mangapassion.fetch_manga_metadata(series_name, vol_num)
        except Exception:
            return None

    async def _none():
        return None

    vol_nums = [
        int(item.volume_number) if item.volume_number and item.volume_number.isdigit() else None
        for item in volume_items
    ]
    mp_results = await asyncio.gather(*[
        _fetch_mp(n) if n is not None else _none()
        for n in vol_nums
    ])

    # Apply enrichment and persist changes
    any_changed = False
    for item, mp_data in zip(volume_items, mp_results):
        changed = False
        if mp_data:
            if mp_data.get("cover_url") and not item.cover_url:
                item.cover_url = mp_data["cover_url"]
                changed = True
            if mp_data.get("page_count") and not item.page_count:
                item.page_count = mp_data["page_count"]
                changed = True
            if mp_data.get("volume_title") and not item.volume_title:
                item.volume_title = mp_data["volume_title"]
                changed = True
            if mp_data.get("authors") and not item.authors:
                item.authors = mp_data["authors"]
                changed = True
            if mp_data.get("publication_year") and not item.publication_year:
                item.publication_year = mp_data["publication_year"]
                changed = True
        elif anilist_data and anilist_data.get("cover_url") and not item.cover_url:
            item.cover_url = anilist_data["cover_url"]
            changed = True

        if changed:
            db.add(item)
            any_changed = True

    if any_changed:
        await db.commit()
        # Reload with fresh eager-loaded data
        result = await db.execute(
            select(models.Item).options(*_ITEM_LOAD).where(models.Item.id.in_(item_ids))
        )
        id_to_item = {i.id: i for i in result.scalars().unique().all()}
        volume_items = [id_to_item.get(i.id, i) for i in volume_items]
        log.info("Enriched %s boxset volumes for series '%s'", len(volume_items), series_name)

    return volume_items


async def _build_boxset_response(
    db: AsyncSession,
    box,
    source: str,
    volume_items=None,
    user_id: int | None = None,
) -> schemas.BoxSetImportResponse:
    """Build a BoxSetImportResponse from a BoxSet ORM object."""
    if volume_items is None:
        # Reload volumes from DB (cached path)
        result = await db.execute(
            select(models.Item)
            .options(*_ITEM_LOAD)
            .where(models.Item.box_set_id == box.id)
        )
        volume_items = result.scalars().unique().all()

    # Sort numerically (volume_number is stored as string)
    volume_items = sorted(
        volume_items,
        key=lambda v: int(v.volume_number) if v.volume_number and v.volume_number.isdigit() else 0,
    )

    # Check which volumes the user already has in their library
    already_in_library_ids = []
    if user_id is not None:
        for vol in volume_items:
            entry = await crud.get_user_item_by_item_id(db, user_id, vol.id)
            if entry:
                already_in_library_ids.append(vol.id)

    box_read = schemas.BoxSetRead.model_validate(box)
    volumes_read = [schemas.ItemRead.model_validate(v) for v in volume_items]
    return schemas.BoxSetImportResponse(
        source=source,
        title=box.name or "",
        cover_url=box.cover_url,
        authors=[],
        box_set=box_read,
        box_volumes=volumes_read,
        volume_count=len(volumes_read),
        already_in_library_ids=already_in_library_ids,
    )


def _apply_mangapassion(metadata: dict, mp_data: dict) -> None:
    """Merge manga-passion data into the metadata dict in-place.

    Manga-passion provides official German publisher (Carlsen) data and wins for
    cover_url (overrides AniList thumbnails with publisher-quality art), series_name,
    and volume_title. Everything else only fills gaps.
    """
    # Cover: official publisher cover beats everything
    if mp_data.get("cover_url"):
        metadata["cover_url"] = mp_data["cover_url"]

    # Canonical German series name and volume subtitle always win
    for field in ("series_name", "volume_title"):
        if mp_data.get(field):
            metadata[field] = mp_data[field]

    # volume_number: fill if missing (manga-passion is authoritative when found by title)
    if mp_data.get("volume_number") is not None and not metadata.get("volume_number"):
        metadata["volume_number"] = str(mp_data["volume_number"])

    # Fill remaining gaps only
    for field in ("authors", "page_count", "publication_year"):
        if not metadata.get(field) and mp_data.get(field):
            metadata[field] = mp_data[field]

    # Store manga-passion IDs for potential future use
    for field in ("mp_volume_id", "mp_edition_id"):
        if mp_data.get(field) is not None:
            metadata[field] = mp_data[field]
