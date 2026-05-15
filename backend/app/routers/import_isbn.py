import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, dnb, schemas
from ..deps import get_db_session
from ..auth import get_current_user

log = logging.getLogger("bookspace.isbn")
router = APIRouter()


@router.post("/isbn", response_model=schemas.ISBNImportResponse, status_code=201)
async def import_by_isbn(
    import_in: schemas.ISBNImportRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: schemas.UserRead = Depends(get_current_user),
):
    """
    Import a book or manga by ISBN.

    Lookup order:
      1. DNB (Deutsche Nationalbibliothek) — queried in parallel.
         Best source for German manga: series title, volume number,
         Inhaltsangabe (520), chapter list (505), demographic (650).
      2. Google Books / Open Library (existing fallback chain in crud).

    When the result is identified as a manga (media_type == "manga"),
    a MangaVolume row is automatically created with all available
    manga-specific fields (original title, demographic, chapters, …).
    """
    isbn = import_in.isbn.strip()
    log.info("ISBN import: '%s' (user=%s)", isbn, current_user.id)

    if not isbn:
        raise HTTPException(status_code=400, detail="ISBN must not be empty.")

    # ── Query DNB and Google/OL in parallel, then merge ─────────────────────
    try:
        dnb_result, (google_ol_result, google_ol_source) = await asyncio.gather(
            dnb.fetch_dnb_by_isbn(isbn),
            _fetch_google_or_ol(isbn),
            return_exceptions=False,
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

    # ── Persist Item ─────────────────────────────────────────────────────────
    try:
        item_in = schemas.ItemCreate(
            **{k: v for k, v in metadata.items() if k in schemas.ItemCreate.model_fields}
        )
        item = await crud.create_item(db, item_in)
    except SQLAlchemyError:
        log.error("Database error saving ISBN import for '%s'", isbn, exc_info=True)
        raise HTTPException(status_code=500, detail="Metadata found but could not be saved. Please try again.")

    # ── Auto-create MangaVolume when media_type == "manga" ───────────────────
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
            # Non-fatal: the Item was saved; manga metadata can be added later

    # Reload with manga_meta relation populated, then build response.
    # Expire the instance first so selectinload bypasses the identity-map cache
    # (important when manga_meta was None on first load and then created in this request).
    item_id_val = item.id
    db.expire(item)
    item = await crud.get_item(db, item_id_val)
    item_data = schemas.ItemRead.model_validate(item)
    return schemas.ISBNImportResponse(**item_data.model_dump(), source=source, raw_metadata=metadata)


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
    """
    Merge DNB and Google/OL results into one dict.

    Priority rules:
    - DNB wins for: series_name, volume_number, volume_title, page_count,
      description, original_title, demographic, dnb_id, chapters, media_type.
    - Google/OL wins for: cover_url (DNB has none), and any field DNB left None.
    - If only one source returned data, use it directly.
    """
    if dnb_data and google_ol_data:
        merged = dict(google_ol_data)   # start with Google/OL as base
        # DNB fields that take priority when present
        dnb_preferred = (
            "media_type", "series_name", "volume_number", "volume_title",
            "page_count", "description", "original_title", "romanized_title",
            "demographic", "dnb_id", "chapters", "language",
        )
        for key in dnb_preferred:
            if dnb_data.get(key) is not None:
                merged[key] = dnb_data[key]
        # DNB title is more precise (includes $n/$p structure)
        if dnb_data.get("title"):
            merged["title"] = dnb_data["title"]
        source = f"dnb+{google_ol_source}"
        return merged, source

    if dnb_data:
        return dnb_data, "dnb"

    if google_ol_data:
        return google_ol_data, google_ol_source

    raise ValueError(
        "No metadata found for this ISBN in any source (DNB, Google Books, Open Library). "
        "You can add the item manually."
    )
