"""Manga-Passion API client for German manga edition metadata.

Public API: https://api.manga-passion.de
No authentication required.

Used as enrichment source when the ISBN is identified as manga.
Provides: canonical German series title, German volume subtitle, high-quality
Carlsen cover images, and author names in western order.

Note: the /volumes?isbn= endpoint returns unreliable results (maps ISBNs to
wrong editions). We search by edition title instead and match by volume number.
"""
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("bookspace.mangapassion")

_BASE = "https://api.manga-passion.de"
_HEADERS = {"User-Agent": "Bookspace/1.0 (personal library tracker)"}
_TIMEOUT = 10

# format=0 → print editions (not digital/eBook)
_PRINT_FORMAT = 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def fetch_manga_metadata(
    series_name: str,
    volume_number: Optional[int],
    volume_title: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find a German print edition by series title and return volume-level metadata.

    When volume_number is known it is used directly. When it is None but
    volume_title is given the volume is located by fuzzy title match within the
    edition. Returns None when nothing matches. All errors are non-fatal.
    """
    if not series_name:
        return None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            edition_id = await _search_best_edition(client, series_name)
            if edition_id is None:
                log.debug("MangaPassion: no edition found for %r", series_name)
                return None

            if volume_number is not None:
                vol = await _fetch_volume(client, edition_id, volume_number)
                if vol is None:
                    log.debug("MangaPassion: vol %s not found in edition %s", volume_number, edition_id)
                    return None
            elif volume_title:
                vol = await _fetch_volume_by_title(client, edition_id, volume_title)
                if vol is None:
                    log.debug("MangaPassion: title %r not found in edition %s", volume_title, edition_id)
                    return None
            else:
                log.debug("MangaPassion: edition %s found but no volume_number or volume_title given", edition_id)
                return None

            return _parse_volume(vol, edition_id)

    except httpx.TimeoutException:
        log.warning("MangaPassion: request timed out for series=%r", series_name)
        return None
    except httpx.RequestError as exc:
        log.warning("MangaPassion: network error for series=%r — %s", series_name, exc)
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _search_best_edition(client: httpx.AsyncClient, series_name: str) -> Optional[int]:
    """Search manga-passion for German print editions matching series_name.

    Returns the id of the best-matching edition, or None.
    """
    resp = await client.get(
        f"{_BASE}/editions",
        params={"title": series_name, "format": _PRINT_FORMAT, "itemsPerPage": 30},
    )
    if resp.status_code != 200:
        log.warning("MangaPassion editions search HTTP %s for %r", resp.status_code, series_name)
        return None

    data = resp.json()
    editions: List[Dict] = data if isinstance(data, list) else data.get("hydra:member", [])
    if not editions:
        return None

    name_lower = series_name.lower()
    best_id: Optional[int] = None
    best_score: float = 0.0

    for ed in editions:
        ed_title = ed.get("title") or ""
        score = SequenceMatcher(None, name_lower, ed_title.lower()).ratio()
        if score > best_score:
            best_score = score
            best_id = ed.get("id")

    # Require at least 0.5 similarity to avoid false positives
    if best_score < 0.5:
        log.debug("MangaPassion: best match score %.2f below threshold for %r", best_score, series_name)
        return None

    log.debug("MangaPassion: edition id=%s (score=%.2f) for %r", best_id, best_score, series_name)
    return best_id


async def _fetch_volume(
    client: httpx.AsyncClient,
    edition_id: int,
    volume_number: int,
) -> Optional[Dict[str, Any]]:
    """Fetch all volumes for an edition and return the one matching volume_number."""
    resp = await client.get(
        f"{_BASE}/editions/{edition_id}/volumes",
        params={"itemsPerPage": 1000},
    )
    if resp.status_code != 200:
        log.warning("MangaPassion volumes HTTP %s for edition %s", resp.status_code, edition_id)
        return None

    data = resp.json()
    volumes: List[Dict] = data if isinstance(data, list) else data.get("hydra:member", [])
    for vol in volumes:
        if vol.get("number") == volume_number:
            return vol
    return None


async def _fetch_volume_by_title(
    client: httpx.AsyncClient,
    edition_id: int,
    volume_title: str,
) -> Optional[Dict[str, Any]]:
    """Find a volume within an edition by fuzzy title match (≥0.5 threshold)."""
    resp = await client.get(
        f"{_BASE}/editions/{edition_id}/volumes",
        params={"itemsPerPage": 1000},
    )
    if resp.status_code != 200:
        log.warning("MangaPassion volumes HTTP %s for edition %s", resp.status_code, edition_id)
        return None

    data = resp.json()
    volumes: List[Dict] = data if isinstance(data, list) else data.get("hydra:member", [])
    title_lower = volume_title.lower()
    best_vol: Optional[Dict] = None
    best_score: float = 0.0
    for vol in volumes:
        vt = vol.get("title") or ""
        score = SequenceMatcher(None, title_lower, vt.lower()).ratio()
        if score > best_score:
            best_score = score
            best_vol = vol

    if best_score < 0.5:
        log.debug("MangaPassion: title match %.2f below threshold for %r in edition %s",
                  best_score, volume_title, edition_id)
        return None

    log.debug("MangaPassion: title match %.2f for %r → vol %s", best_score, volume_title,
              best_vol.get("number") if best_vol else None)
    return best_vol


def _parse_volume(vol: Dict[str, Any], edition_id: int) -> Dict[str, Any]:
    """Extract enrichment fields from a manga-passion volume object."""
    edition = vol.get("edition") or {}

    # Collect authors from all sources → contributors (deduplicated, western order)
    authors: List[str] = []
    seen: set = set()
    for source in edition.get("sources") or []:
        for contrib in source.get("contributors") or []:
            name = (contrib.get("contributor") or {}).get("name")
            if name and name not in seen:
                authors.append(name)
                seen.add(name)

    result: Dict[str, Any] = {
        "series_name": edition.get("title"),
        "volume_title": vol.get("title"),
        "volume_number": vol.get("number"),
        "cover_url": vol.get("cover"),
        "publication_year": vol.get("year"),
        "page_count": vol.get("pages"),
        "mp_volume_id": vol.get("id"),
        "mp_edition_id": edition_id,
    }
    if authors:
        result["authors"] = authors

    log.info(
        "MangaPassion: vol %s '%s' from edition '%s' (cover=%s)",
        vol.get("number"),
        vol.get("title"),
        edition.get("title"),
        "yes" if result["cover_url"] else "no",
    )
    return result
