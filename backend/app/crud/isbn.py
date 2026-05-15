import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import settings

log = logging.getLogger("bookspace.isbn")

# Module-level alias so tests can patch it without touching config
GOOGLE_BOOKS_API_KEY: str = settings.google_books_api_key

SERIES_PATTERNS = [
    r"(?P<series>.+?)\s+Vol(?:ume)?\.?\s*(?P<volume>\d+)",
    r"(?P<series>.+?)\s+Band\s*(?P<volume>\d+)",
    r"(?P<series>.+?)\s+#(?P<volume>\d+)",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def get_isbn_from_info(volume_info: Dict[str, Any]) -> Optional[str]:
    """Return the first ISBN-13 or ISBN-10 from a Google Books volumeInfo dict."""
    for identifier in volume_info.get("industryIdentifiers", []):
        if identifier.get("type") in ("ISBN_13", "ISBN_10"):
            return identifier.get("identifier")
    return None


def extract_series_fields(title: str, subtitle: Optional[str]) -> Dict[str, Any]:
    """Detect series name and volume number from a book title / subtitle."""
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


# ---------------------------------------------------------------------------
# Source parsers
# ---------------------------------------------------------------------------

def parse_google_book(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a single Google Books API item into our internal metadata dict."""
    info = item.get("volumeInfo", {})
    title = info.get("title", "")
    pub_date = info.get("publishedDate", "")
    try:
        pub_year = int(pub_date[:4]) if pub_date else None
    except (ValueError, TypeError):
        pub_year = None

    cats = info.get("categories", [])
    img = info.get("imageLinks", {})

    return {
        "title": title,
        "authors": info.get("authors", []),
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
    """Normalise an Open Library /api/books entry into our internal metadata dict."""
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
    subjects = [
        s["name"] for s in data.get("subjects", [])
        if isinstance(s, dict) and s.get("name")
    ]
    excerpts = data.get("excerpts", [])

    return {
        "title": title,
        "authors": authors,
        "publication_year": pub_year,
        "genre": ", ".join(subjects[:3]) if subjects else None,
        "page_count": data.get("number_of_pages"),
        "description": excerpts[0].get("text") if excerpts else None,
        "isbn": isbn,
        "cover_url": cover.get("large") or cover.get("medium") or cover.get("small"),
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


# ---------------------------------------------------------------------------
# Main ISBN lookup (Google Books → Open Library fallback)
# ---------------------------------------------------------------------------

async def parse_isbn_metadata(isbn: str) -> Tuple[Dict[str, Any], str]:
    """Look up book metadata by ISBN via Google Books then Open Library.

    Returns ``(metadata_dict, source_name)`` on success.
    Raises ``ValueError`` with a user-friendly message when all sources fail.
    Raises ``httpx.RequestError`` on unrecoverable network failures.
    """
    sanitized = re.sub(r"[^0-9Xx]", "", isbn)
    if not sanitized:
        raise ValueError("Invalid ISBN: no digits found.")
    if len(sanitized) not in (10, 13):
        raise ValueError(f"Invalid ISBN length ({len(sanitized)} digits). Expected 10 or 13.")

    log.info("ISBN lookup started — raw=%r sanitized=%r", isbn, sanitized)

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
                    log.debug("Google Books: querying with API key")
                else:
                    log.debug("Google Books: querying without API key (shared quota)")

                google_resp = await client.get(
                    "https://www.googleapis.com/books/v1/volumes", params=google_params
                )
                log.debug("Google Books: HTTP %s", google_resp.status_code)

                if google_resp.status_code == 200:
                    data = google_resp.json()
                    if data.get("totalItems", 0) > 0:
                        book = parse_google_book(data["items"][0])
                        log.info("Google Books: found '%s'", book.get("title"))
                        return book, "google"
                    log.warning("Google Books: no results for ISBN %s", sanitized)
                    google_error = "Google Books returned no results for this ISBN."
                elif google_resp.status_code == 429:
                    log.warning(
                        "Google Books: rate limited (429) — %s API key",
                        "with" if GOOGLE_BOOKS_API_KEY else "without",
                    )
                    google_rate_limited = True
                    google_error = (
                        "Google Books API key quota exceeded."
                        if GOOGLE_BOOKS_API_KEY
                        else "Google Books daily quota exceeded."
                    )
                elif google_resp.status_code == 400:
                    msg = google_resp.json().get("error", {}).get("message", "Bad request")
                    log.error("Google Books: 400 Bad Request — %s", msg)
                    google_error = f"Google Books rejected the request: {msg}"
                elif google_resp.status_code == 403:
                    log.error("Google Books: 403 Forbidden")
                    google_error = (
                        "Google Books API key is invalid or the Books API is not enabled in Google Cloud."
                    )
                else:
                    log.warning("Google Books: unexpected HTTP %s", google_resp.status_code)
                    google_error = f"Google Books returned HTTP {google_resp.status_code}."

            except httpx.TimeoutException:
                log.warning("Google Books: request timed out")
                google_error = "Google Books request timed out."
            except httpx.ConnectError as exc:
                log.warning("Google Books: connection error — %s", exc)
                google_error = "Could not connect to Google Books."
            except httpx.RequestError as exc:
                log.warning("Google Books: network error — %s", exc)
                google_error = f"Google Books network error: {exc}"

            # ── Open Library ────────────────────────────────────────────────
            try:
                log.debug("Open Library: querying for ISBN %s", sanitized)
                ol_resp = await client.get(
                    "https://openlibrary.org/api/books",
                    params={"bibkeys": f"ISBN:{sanitized}", "jscmd": "data", "format": "json"},
                )
                log.debug("Open Library: HTTP %s", ol_resp.status_code)

                if ol_resp.status_code == 200:
                    data = ol_resp.json()
                    key = f"ISBN:{sanitized}"
                    if key in data:
                        book = parse_open_library_api(data[key], sanitized)
                        log.info("Open Library: found '%s'", book.get("title"))
                        return book, "openlibrary"
                    log.warning("Open Library: no entry for key '%s'", key)
                    ol_error = "Open Library has no record for this ISBN."
                else:
                    log.warning("Open Library: unexpected HTTP %s", ol_resp.status_code)
                    ol_error = f"Open Library returned HTTP {ol_resp.status_code}."

            except httpx.TimeoutException:
                log.warning("Open Library: request timed out")
                ol_error = "Open Library request timed out."
            except httpx.ConnectError as exc:
                log.warning("Open Library: connection error — %s", exc)
                ol_error = "Could not connect to Open Library."
            except httpx.RequestError as exc:
                log.warning("Open Library: network error — %s", exc)
                ol_error = f"Open Library network error: {exc}"

    except Exception as exc:
        log.error("ISBN lookup: unexpected error for %r — %s", sanitized, exc, exc_info=True)
        raise ValueError(f"Unexpected error during ISBN lookup: {exc}") from exc

    # ── All sources exhausted ────────────────────────────────────────────────
    log.error(
        "ISBN lookup failed for %s — Google: %s | OpenLibrary: %s",
        sanitized, google_error, ol_error,
    )

    parts: List[str] = []
    if google_rate_limited:
        parts.append(
            "Google Books API key quota is exhausted — check your billing or wait for it to reset."
            if GOOGLE_BOOKS_API_KEY
            else (
                "Google Books daily quota is exhausted (shared anonymous limit). "
                "Add a free GOOGLE_BOOKS_API_KEY to .env for a dedicated quota."
            )
        )
    elif google_error:
        parts.append(f"Google Books: {google_error}")

    if ol_error:
        parts.append(f"Open Library: {ol_error}")

    if not parts:  # pragma: no cover
        parts.append("No metadata found for this ISBN.")

    parts.append("You can add the book manually using the manual entry tab.")
    raise ValueError(" | ".join(parts))
