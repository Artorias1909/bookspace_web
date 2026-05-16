"""AniList GraphQL client for manga metadata enrichment.

AniList is used as a secondary source when the ISBN lookup identifies
a manga title. Primary value: high-resolution cover images and Japanese
original titles — both of which DNB and Google Books lack.

Public API: https://anilist.gitbook.io/anilist-apiv2-docs/
GraphQL endpoint: https://graphql.anilist.co (no authentication required)
"""
import logging
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger("bookspace.anilist")

_ENDPOINT = "https://graphql.anilist.co"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Bookspace/1.0 (personal library tracker)",
}

_QUERY = """
query ($search: String) {
  Media(search: $search, type: MANGA) {
    title { romaji english native }
    coverImage { large medium }
    startDate { year }
    staff(sort: RELEVANCE, perPage: 5) {
      edges {
        role
        node { name { full } }
      }
    }
  }
}
"""


async def fetch_anilist_by_title(title: str) -> Optional[Dict[str, Any]]:
    """Search AniList for a manga by (series) title.

    Returns a partial metadata dict with cover_url, original_title,
    romanized_title, and publication_year — or None when nothing is found
    or the network request fails.
    """
    if not title:
        return None

    try:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
            resp = await client.post(
                _ENDPOINT,
                json={"query": _QUERY, "variables": {"search": title}},
            )
            log.debug("AniList: HTTP %s for title=%r", resp.status_code, title)

            if resp.status_code != 200:
                log.warning("AniList: unexpected HTTP %s for title=%r", resp.status_code, title)
                return None

            media = resp.json().get("data", {}).get("Media")
            if not media:
                log.debug("AniList: no result for title=%r", title)
                return None

            return _parse(media, title)

    except httpx.TimeoutException:
        log.warning("AniList: request timed out for title=%r", title)
        return None
    except httpx.RequestError as exc:
        log.warning("AniList: network error for title=%r — %s", title, exc)
        return None


def _parse(media: Dict[str, Any], searched_title: str) -> Dict[str, Any]:
    titles = media.get("title", {})
    cover = media.get("coverImage", {})
    start = media.get("startDate") or {}

    cover_url = cover.get("large") or cover.get("medium")
    original_title = titles.get("native")   # Japanese (kanji/kana)
    romanized_title = titles.get("romaji")  # e.g. "Naruto"
    pub_year = start.get("year")

    # Authors: prefer Writer/Story role, fall back to any credited staff
    authors = []
    seen = set()
    for edge in media.get("staff", {}).get("edges", []):
        node = edge.get("node", {})
        full = node.get("name", {}).get("full")
        if full and full not in seen:
            authors.append(full)
            seen.add(full)

    result: Dict[str, Any] = {
        "cover_url":      cover_url,
        "original_title": original_title,
        "romanized_title": romanized_title,
        "publication_year": pub_year,
    }
    # Only include authors if we found any (don't overwrite DNB's more precise data)
    if authors:
        result["authors"] = authors

    log.info(
        "AniList: found '%s' (cover=%s, native=%r)",
        romanized_title or searched_title,
        "yes" if cover_url else "no",
        original_title,
    )
    return result
