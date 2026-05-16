"""DNB (Deutsche Nationalbibliothek) SRU API client.

Public SRU endpoint: https://services.dnb.de/sru/dnb
Documentation:       https://www.dnb.de/sru

The DNB catalog is the most reliable source for German manga editions.
It carries:
  - Series title and volume number (MARC 490/830)
  - Japanese original title (MARC 246)
  - Table of contents / chapters (MARC 505)
  - Description / Inhaltsangabe (MARC 520)
  - Page count (MARC 300 $a)
  - Demographic (from MARC 650 subject headings, e.g. "Shōnen-Manga")
  - Publisher and publication year (MARC 264)

Animexx (animexx.de) does not expose a documented public REST API.
Cross-referencing via Animexx would require HTML scraping, which is
fragile and potentially against their ToS. The DNB already covers the
metadata that matters for a German manga collection; Animexx can be
added later with an `animexx_id` already reserved in MangaVolume.
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("bookspace.dnb")

_SRU_BASE = "https://services.dnb.de/sru/dnb"
_MARC_NS = "http://www.loc.gov/MARC21/slim"
_HEADERS = {"User-Agent": "Bookspace/1.0 (personal library tracker; contact: bookspace-app)"}

# DNB 650 subject-heading → internal demographic key
_DEMOGRAPHIC_MAP: Dict[str, str] = {
    "shōnen-manga": "shounen",
    "shounen-manga": "shounen",
    "shônen-manga":  "shounen",
    "shōjo-manga":   "shoujo",
    "shoujo-manga":  "shoujo",
    "shôjo-manga":   "shoujo",
    "seinen-manga":  "seinen",
    "josei-manga":   "josei",
    "kodomomuke":    "kodomomuke",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def fetch_dnb_by_isbn(isbn: str) -> Optional[Dict[str, Any]]:
    """Query DNB SRU for a single ISBN. Returns parsed metadata dict or None."""
    params = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": f"nid={isbn}",
        "recordSchema": "MARC21-xml",
        "maximumRecords": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
            response = await client.get(_SRU_BASE, params=params)
            log.debug("DNB SRU: HTTP %s for ISBN %s", response.status_code, isbn)
            if response.status_code != 200:
                log.warning("DNB SRU: unexpected HTTP %s for ISBN %s", response.status_code, isbn)
                return None
            return _parse_sru_response(response.content, isbn_fallback=isbn)
    except httpx.TimeoutException:
        log.warning("DNB SRU: timed out for ISBN %s", isbn)
        return None
    except httpx.RequestError as exc:
        log.warning("DNB SRU: network error for ISBN %s — %s", isbn, exc)
        return None


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------

def _parse_sru_response(xml_bytes: bytes, isbn_fallback: str = "") -> Optional[Dict[str, Any]]:
    """Parse a full DNB SRU MARC21-xml response into a metadata dict."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        log.error("DNB: failed to parse XML — %s", exc)
        return None

    marc_record = root.find(f".//{{{_MARC_NS}}}record")
    if marc_record is None:
        log.debug("DNB: no MARC record in SRU response")
        return None

    return _parse_marc_record(marc_record, isbn_fallback)


def _parse_marc_record(record: ET.Element, isbn_fallback: str = "") -> Dict[str, Any]:
    """Extract all relevant fields from a single MARC21 <record> element."""

    def fields(tag: str) -> List[ET.Element]:
        return record.findall(f"{{{_MARC_NS}}}datafield[@tag='{tag}']")

    def sub(field: ET.Element, code: str) -> Optional[str]:
        el = field.find(f"{{{_MARC_NS}}}subfield[@code='{code}']")
        return el.text.strip() if el is not None and el.text else None

    def ctrlfield(tag: str) -> Optional[str]:
        el = record.find(f"{{{_MARC_NS}}}controlfield[@tag='{tag}']")
        return el.text.strip() if el is not None and el.text else None

    # ── DNB record ID (001) ───────────────────────────────────────────────
    dnb_id = ctrlfield("001")

    # ── ISBN (020 $a) ─────────────────────────────────────────────────────
    isbn = isbn_fallback
    for f in fields("020"):
        raw = sub(f, "a")
        if raw:
            # Strip qualifiers like "(Gb.)" or "(kart.)"
            isbn = re.sub(r"\s*\(.*?\)", "", raw).strip()
            break

    # ── Title (245) ───────────────────────────────────────────────────────
    # $a = main title  $b = remainder/subtitle  $n = part number  $p = part name
    title = ""
    volume_number_from_245: Optional[str] = None
    volume_title: Optional[str] = None
    for f in fields("245"):
        title = (sub(f, "a") or "").rstrip(" /:")
        volume_number_from_245 = sub(f, "n")
        volume_title = sub(f, "p")
        break

    # ── Original / alternate titles (246) ─────────────────────────────────
    # Indicator 2 = 3 means "Other title", often the Japanese original
    original_title: Optional[str] = None
    romanized_title: Optional[str] = None
    for f in fields("246"):
        val = sub(f, "a")
        if not val:
            continue
        ind2 = f.get("ind2", " ")
        # Heuristic: contains CJK characters → Japanese original
        if re.search(r"[　-鿿＀-￯]", val):
            original_title = val
        elif ind2 == "3" and not original_title:
            # "Other title" indicator, likely romanized
            romanized_title = val
        elif not original_title:
            original_title = val

    # ── Series (490 preferred, 830 fallback) ─────────────────────────────
    # 490 $a = series title  $v = volume number
    # 830 $a = series title  $v = volume number (authoritative added entry)
    series_name: Optional[str] = None
    series_volume: Optional[str] = None
    for tag in ("490", "830"):
        for f in fields(tag):
            s_name = sub(f, "a")
            if s_name:
                series_name = s_name.rstrip(" /:")
                series_volume = sub(f, "v")
                break
        if series_name:
            break

    # Volume number: prefer 490/830 $v, fall back to 245 $n.
    # Normalize raw strings like "Band 1", "Bd. 03", "Vol. 1" → "1", "3", "1".
    volume_number = _normalize_volume_number(series_volume or volume_number_from_245)

    # ── Authors (100 = main entry, 700 = additional) ──────────────────────
    authors: List[str] = []
    seen_authors: set = set()
    for tag in ("100", "700"):
        for f in fields(tag):
            name = sub(f, "a")
            if name and name not in seen_authors:
                # Normalize "Familienname, Vorname" → "Vorname Familienname"
                parts = [p.strip().rstrip(",") for p in name.split(",", 1)]
                display = f"{parts[1]} {parts[0]}" if len(parts) == 2 else parts[0]
                authors.append(display)
                seen_authors.add(name)

    # ── Publication year ──────────────────────────────────────────────────
    # 264 $c = "2024" or "© 2024" — preferred for modern records
    pub_year: Optional[int] = None
    for f in fields("264"):
        val = sub(f, "c")
        if val:
            m = re.search(r"\d{4}", val)
            if m:
                pub_year = int(m.group())
                break
    if not pub_year:
        # MARC 008 fixed-length: positions 7–10 are the year of publication
        f008 = ctrlfield("008")
        if f008 and len(f008) >= 11:
            try:
                pub_year = int(f008[7:11])
            except ValueError:
                pass

    # ── Page count (300 $a) ───────────────────────────────────────────────
    # Examples: "228 Seiten", "192 S.", "[192] Seiten"
    page_count: Optional[int] = None
    for f in fields("300"):
        extent = sub(f, "a") or ""
        m = re.search(r"(\d+)\s*(?:Seiten?|pages?|S\.)", extent, re.IGNORECASE)
        if m:
            page_count = int(m.group(1))
        else:
            m2 = re.search(r"\d+", extent)
            if m2:
                page_count = int(m2.group())
        if page_count:
            break

    # ── Description / Inhaltsangabe (520 $a) ─────────────────────────────
    description: Optional[str] = None
    for f in fields("520"):
        description = sub(f, "a")
        if description:
            break

    # ── Table of contents / chapters (505) ───────────────────────────────
    # 505 ind1=0 → complete contents note
    # Subfield $a = formatted string; enhanced 505 also uses $t per chapter
    toc_parts: List[str] = []
    for f in fields("505"):
        # Collect $t subfields first (enhanced 505 — each is a chapter title)
        t_subs = [
            el.text.strip()
            for el in f.findall(f"{{{_MARC_NS}}}subfield[@code='t']")
            if el.text
        ]
        if t_subs:
            toc_parts.extend(t_subs)
        else:
            raw = sub(f, "a")
            if raw:
                toc_parts.append(raw)

    chapters = _parse_chapters("\n".join(toc_parts)) if toc_parts else []

    # ── Language (041 $a) ─────────────────────────────────────────────────
    language: Optional[str] = None
    for f in fields("041"):
        language = sub(f, "a")
        if language:
            break

    # ── Subject headings / demographic (650) ─────────────────────────────
    subject_tags: List[str] = []
    demographic: Optional[str] = None
    for f in fields("650"):
        val = sub(f, "a")
        if val:
            subject_tags.append(val)
            lower = val.lower()
            for key, demo in _DEMOGRAPHIC_MAP.items():
                if key in lower:
                    demographic = demo
                    break

    genre = ", ".join(subject_tags[:3]) if subject_tags else None

    # ── Derive media_type ─────────────────────────────────────────────────
    media_type = _detect_media_type(subject_tags, title)

    log.info(
        "DNB parsed: dnb_id=%s title=%r series=%r vol=%r pages=%s chapters=%s media_type=%s",
        dnb_id, title, series_name, volume_number, page_count, len(chapters), media_type,
    )

    return {
        # Item fields
        "media_type": media_type,
        "title": title or volume_title or "",
        "authors": authors,
        "publication_year": pub_year,
        "genre": genre,
        "page_count": page_count,
        "description": description,
        "isbn": isbn,
        "cover_url": None,   # DNB SRU does not provide cover images
        "language": language,
        "volume_number": volume_number,
        "volume_title": volume_title or title,
        # Series (name only — caller resolves / creates the Series row)
        "series_name": series_name,
        # MangaVolume-specific fields
        "original_title": original_title,
        "romanized_title": romanized_title,
        "demographic": demographic,
        "dnb_id": dnb_id,
        "chapters": chapters,
    }


# ---------------------------------------------------------------------------
# Volume number normalisation
# ---------------------------------------------------------------------------

def _normalize_volume_number(raw: Optional[str]) -> Optional[str]:
    """Extract a clean numeric string from MARC 490/830 $v values.

    Handles: "Band 1", "Bd. 03", "Vol. 2", "1.", "1.5", "12" → "1", "3", "2", "1", "1.5", "12"
    Leading zeros are removed ("03" → "3"). Decimal volumes are preserved ("1.5").
    """
    if not raw:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", raw)
    if not m:
        return raw.strip()
    num = m.group(1).replace(",", ".")
    fval = float(num)
    return str(int(fval)) if fval == int(fval) else str(fval)


# ---------------------------------------------------------------------------
# Chapter parsing
# ---------------------------------------------------------------------------

# Matches: "Kapitel 3: Titel", "Chapter 3: Titel", "Ep. 3 Titel", "3. Titel"
_CHAPTER_LABELLED = re.compile(
    r"(?:Kapitel|Chapter|Kap\.?|Episode|Ep\.?)\s*(\d+(?:[.,]\d+)?)\s*[:.]\s*(.+)",
    re.IGNORECASE,
)
_CHAPTER_NUMBERED = re.compile(r"^(\d+(?:[.,]\d+)?)[.\s\-–]+(.+)")


def _parse_chapters(toc: str) -> List[Dict[str, Any]]:
    """
    Parse chapter entries from a MARC 505 table-of-contents string.

    DNB uses two formats:
      Basic 505 $a:  "Kapitel 1: Titel -- Kapitel 2: Titel -- …"
      Enhanced 505:  individual $t subfields already split by the caller.

    Returns list of dicts compatible with ChapterEntryCreate.
    """
    # Split on double dash (MARC convention), semicolons, or newlines
    parts = re.split(r"\s*--\s*|\s*;\s*|\n", toc)
    chapters: List[Dict[str, Any]] = []

    for i, raw in enumerate(parts):
        part = raw.strip().rstrip(". ")
        if not part or len(part) < 2:
            continue

        m = _CHAPTER_LABELLED.match(part)
        if m:
            num = m.group(1).replace(",", ".")
            chapters.append({"order_index": i, "chapter_number": num, "title": m.group(2).strip()})
            continue

        m = _CHAPTER_NUMBERED.match(part)
        if m:
            num = m.group(1).replace(",", ".")
            chapters.append({"order_index": i, "chapter_number": num, "title": m.group(2).strip()})
            continue

        # Unstructured entry — store title only (e.g. "Extras", "Bonus-Kapitel")
        chapters.append({"order_index": i, "chapter_number": None, "title": part})

    return chapters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_media_type(subject_tags: List[str], title: str) -> str:
    """Heuristic: determine media_type from DNB subject headings and title."""
    combined = " ".join(subject_tags + [title]).lower()
    if "manga" in combined:
        return "manga"
    if "comic" in combined or "graphic novel" in combined:
        return "comic"
    return "book"
