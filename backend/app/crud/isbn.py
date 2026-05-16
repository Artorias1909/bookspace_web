import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import settings

log = logging.getLogger("bookspace.isbn")

# Module-level alias so tests can patch it without touching config
GOOGLE_BOOKS_API_KEY: str = settings.google_books_api_key

# ---------------------------------------------------------------------------
# Boxset detection
# ---------------------------------------------------------------------------

# Keywords in the title that indicate a collector box / Sammelschuber
_BOXSET_KEYWORDS = [
    "sammelschuber", "sammelband", "sammelbox", "omnibus",
    "box set", "boxset", "collector",
]

# Matches German volume ranges: "Band 1-12", "Bände 13-23", "Bde. 1-3"
_VOL_RANGE_RE = re.compile(
    r"B(?:ä|ae|a)?nde?\.?\s+(\d+)\s*[-–]\s*(\d+)",
    re.IGNORECASE,
)

# Extracts arc name from "Series Sammelschuber N: Arc Name (..."
_ARC_NAME_RE = re.compile(r":\s*([^(,\n]+?)(?:\s*[\(,]|$)", re.IGNORECASE)


def detect_boxset(title: str) -> Optional[Tuple[Optional[str], int, int]]:
    """Return (arc_name, vol_from, vol_to) if title indicates a collector box, else None.

    Example: "One Piece Sammelschuber 1: East Blue (inklusive Band 1-12)"
             → ("East Blue", 1, 12)
    """
    if not any(kw in title.lower() for kw in _BOXSET_KEYWORDS):
        return None
    vol_m = _VOL_RANGE_RE.search(title)
    if not vol_m:
        return None
    arc_m = _ARC_NAME_RE.search(title)
    arc_name = arc_m.group(1).strip() if arc_m else None
    return arc_name, int(vol_m.group(1)), int(vol_m.group(2))


def extract_boxset_series_name(title: str) -> Optional[str]:
    """Extract the series name from a boxset title by taking the part before the keyword.

    Example: "One Piece Sammelschuber 1: East Blue" → "One Piece"
    """
    title_lower = title.lower()
    for kw in _BOXSET_KEYWORDS:
        idx = title_lower.find(kw)
        if idx > 0:
            return title[:idx].strip()
    return None

SERIES_PATTERNS = [
    r"(?P<series>.+?)\s+Vol(?:ume)?\.?\s*(?P<volume>\d+(?:\.\d+)?)",
    r"(?P<series>.+?)\s+Bd\.?\s*(?P<volume>\d+(?:\.\d+)?)",
    r"(?P<series>.+?)\s+Band\s*(?P<volume>\d+(?:\.\d+)?)",
    r"(?P<series>.+?)\s+#(?P<volume>\d+(?:\.\d+)?)",
    # Number in middle — "Harry Potter 3 und der …", "One Piece 5 - Battle"
    # Strip the bare number to reconstruct the proper title (clean_title).
    r"^(?P<series>.+?)\s+(?P<volume>\d+(?:\.\d+)?)\s+\S",
    # Trailing bare number — "One Piece 2", "Naruto 1" (last-resort heuristic)
    r"^(?P<series>.+?)\s+(?P<volume>\d+(?:\.\d+)?)$",
]

# Index of the "number in middle" pattern — when it matches, reconstruct a clean title.
_MIDDLE_NUMBER_PATTERN_IDX = 4

# Maps subject/category keywords to canonical genre tags (first match wins per tag).
# Checked case-insensitively against each raw subject string.
_GENRE_MAP: List[Tuple[List[str], str]] = [
    (["fantasy", "magic", "wizard", "witch", "sorcerer", "dragon", "fairy tale"], "Fantasy"),
    (["science fiction", "sci-fi", "dystopi", "space opera", "cyberpunk"], "Science Fiction"),
    (["juvenile", "young adult", "teen", "children's", "kids"], "Young Adults"),
    (["romance", "love story", "romantic fiction"], "Romance"),
    (["thriller", "suspense"], "Thriller"),
    (["mystery", "detective", "crime fiction", "murder", "whodunit"], "Mystery & Crime"),
    (["horror", "ghost stories"], "Horror"),
    (["adventure"], "Adventure"),
    (["historical fiction", "history -- fiction"], "Historical Fiction"),
    (["biography", "memoir", "autobiography"], "Biography"),
    (["non-fiction", "nonfiction", "self-help"], "Non-Fiction"),
]

# German "Name und der/die/das Subtitle" connector — detects series without volume number.
# Requires at least 2 words before "und" to reduce false positives.
_GERMAN_CONNECTOR_RE = re.compile(
    r"^(?P<series>.+?)\s+und\s+(?:der|die|das|den|dem|des|ein|eine|einer|einen)\s",
    re.IGNORECASE,
)

# OL subject prefixes that signal a known series
_OL_SERIES_PREFIX = "series:"
_OL_FRANCHISE_PREFIX = "franchise:"

# OL subjects → internal media_type
_OL_MEDIA_KEYWORDS = {
    "manga": "manga",
    "graphic novel": "comic",
    "comic": "comic",
}

# OL intended-public subjects → demographic
_OL_DEMOGRAPHIC_MAP = {
    "shōnen": "shounen",
    "shounen": "shounen",
    "shōjo": "shoujo",
    "shoujo": "shoujo",
    "seinen": "seinen",
    "josei": "josei",
    "kodomomuke": "kodomomuke",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _normalize_genre(subjects: List[str]) -> Optional[str]:
    """Map raw OL subjects / Google categories to canonical genre tags (up to 3)."""
    found: List[str] = []
    seen: set = set()
    for subject in subjects:
        sl = subject.lower()
        for keywords, genre in _GENRE_MAP:
            if genre not in seen:
                if any(kw in sl for kw in keywords):
                    found.append(genre)
                    seen.add(genre)
                    break
    return ", ".join(found[:3]) if found else None


def get_isbn_from_info(volume_info: Dict[str, Any]) -> Optional[str]:
    """Return the first ISBN-13 or ISBN-10 from a Google Books volumeInfo dict."""
    for identifier in volume_info.get("industryIdentifiers", []):
        if identifier.get("type") in ("ISBN_13", "ISBN_10"):
            return identifier.get("identifier")
    return None


def extract_series_fields(title: str, subtitle: Optional[str]) -> Dict[str, Any]:
    """Detect series name and volume number from a book title / subtitle.

    Returns a dict with series_name, volume_number, volume_title, series_id.
    For the "number in middle" pattern also returns clean_title with the bare
    volume number stripped (e.g. "Harry Potter 3 und …" → "Harry Potter und …").
    """
    text = " ".join(filter(None, [title, subtitle]))
    for idx, pattern in enumerate(SERIES_PATTERNS):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result: Dict[str, Any] = {
                "series_id": None,
                "series_name": match.group("series").strip(),
                "volume_number": match.group("volume"),
                "volume_title": title,
            }
            if idx == _MIDDLE_NUMBER_PATTERN_IDX:
                # Reconstruct title without the embedded volume number
                vol_start = match.start("volume")
                vol_end = match.end("volume")
                clean = title[:vol_start].rstrip() + " " + title[vol_end:].lstrip()
                result["clean_title"] = clean.strip()
            return result
    # Last-resort: "Name und der/die/das Subtitle" German connector pattern
    m = _GERMAN_CONNECTOR_RE.match(title)
    if m:
        series = m.group("series").strip()
        if " " in series:  # require at least two words to reduce false positives
            return {"series_id": None, "series_name": series, "volume_number": None, "volume_title": title}
    return {"series_id": None, "series_name": None, "volume_number": None, "volume_title": None}


def _extract_series_from_ol_subjects(subjects: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (series_name, media_type, demographic) extracted from OL subject tags."""
    series_name: Optional[str] = None
    media_type: Optional[str] = None
    demographic: Optional[str] = None

    for s in subjects:
        sl = s.lower()
        # Series name
        if series_name is None:
            if sl.startswith(_OL_SERIES_PREFIX):
                series_name = s[len(_OL_SERIES_PREFIX):].strip().replace("_", " ")
            elif sl.startswith(_OL_FRANCHISE_PREFIX):
                series_name = s[len(_OL_FRANCHISE_PREFIX):].strip().replace("_", " ")
        # Media type
        if media_type is None:
            for kw, mt in _OL_MEDIA_KEYWORDS.items():
                if kw in sl:
                    media_type = mt
                    break
        # Demographic — from "intended public:shōnen" etc.
        if demographic is None and "intended public:" in sl:
            pub = sl.split("intended public:", 1)[1].strip()
            demographic = _OL_DEMOGRAPHIC_MAP.get(pub)

    return series_name, media_type, demographic


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
    series_fields = extract_series_fields(title, info.get("subtitle", ""))
    display_title = series_fields.pop("clean_title", None) or title

    return {
        "title": display_title,
        "authors": info.get("authors", []),
        "publication_year": pub_year,
        "genre": _normalize_genre(cats) or (", ".join(cats[:3]) if cats else None),
        "page_count": info.get("pageCount"),
        "description": info.get("description"),
        "isbn": get_isbn_from_info(info),
        "cover_url": img.get("large") or img.get("thumbnail") or img.get("smallThumbnail"),
        "language": info.get("language"),
        **series_fields,
    }


def parse_open_library_api(data: Dict[str, Any], isbn_fallback: str = "") -> Dict[str, Any]:
    """Normalise an Open Library /api/books entry into our internal metadata dict."""
    title = data.get("title", "")
    subtitle = data.get("subtitle", "")
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

    ol_series, ol_media_type, ol_demographic = _extract_series_from_ol_subjects(subjects)

    series_fields = extract_series_fields(title, subtitle)
    display_title = series_fields.pop("clean_title", None) or title

    # OL subtitle is the German volume title (e.g. "Ruffy versus Buggy, der Clown")
    if subtitle:
        series_fields["volume_title"] = subtitle

    # Subject-derived series name overrides the heuristic title extraction
    if ol_series:
        series_fields["series_name"] = ol_series

    return {
        "title": display_title,
        "authors": authors,
        "publication_year": pub_year,
        "genre": _normalize_genre(subjects) or (", ".join(subjects[:3]) if subjects else None),
        "page_count": data.get("number_of_pages"),
        "description": excerpts[0].get("text") if excerpts else None,
        "isbn": isbn,
        "cover_url": cover.get("large") or cover.get("medium") or cover.get("small"),
        "language": None,
        "media_type": ol_media_type or "book",
        "demographic": ol_demographic,
        **series_fields,
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


def _enrich_with_ol(google: Dict[str, Any], ol: Dict[str, Any]) -> Dict[str, Any]:
    """Merge OL structured fields into a Google Books result.

    OL wins for: series_name, volume_number, volume_title, media_type, demographic.
    Google keeps: title, cover_url, authors (unless OL is better), publication_year.
    """
    merged = dict(google)
    for field in ("series_name", "volume_number", "volume_title", "media_type", "demographic"):
        if ol.get(field) is not None:
            merged[field] = ol[field]
    # Use OL cover only as fallback
    if not merged.get("cover_url") and ol.get("cover_url"):
        merged["cover_url"] = ol["cover_url"]
    return merged


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
            google_book: Optional[Dict[str, Any]] = None
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
                        google_book = parse_google_book(data["items"][0])
                        log.info("Google Books: found '%s'", google_book.get("title"))
                    else:
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
                        ol_book = parse_open_library_api(data[key], sanitized)
                        log.info("Open Library: found '%s'", ol_book.get("title"))

                        if google_book is not None:
                            # Both sources succeeded — enrich Google result with OL structure
                            merged = _enrich_with_ol(google_book, ol_book)
                            log.info("Merged Google+OL: series=%r vol=%r",
                                     merged.get("series_name"), merged.get("volume_number"))
                            return merged, "google+openlibrary"

                        # Google failed — OL is the sole result
                        return ol_book, "openlibrary"

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

            # Google succeeded but OL had no data — return Google result alone
            if google_book is not None:
                return google_book, "google"

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
