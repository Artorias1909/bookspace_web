"""Tests for the manga-passion API client."""
import pytest
import respx
import httpx
from unittest.mock import patch

from app import mangapassion

MP_BASE = "https://api.manga-passion.de"
EDITIONS_URL = f"{MP_BASE}/editions"


def _volumes_url(edition_id: int) -> str:
    return f"{MP_BASE}/editions/{edition_id}/volumes"


EDITIONS_RESPONSE = [
    {"id": 87, "title": "One Piece", "format": 0},
    {"id": 88, "title": "One Piece Remix", "format": 0},
]

VOLUME_RESPONSE = [
    {
        "id": 1001,
        "number": 1,
        "title": "Das Abenteuer beginnt",
        "cover": "https://cdn.mp.de/op1.jpg",
        "year": 2001,
        "pages": 200,
        "edition": {
            "title": "One Piece",
            "sources": [
                {
                    "contributors": [
                        {"contributor": {"name": "Eiichiro Oda"}},
                    ]
                }
            ],
        },
    },
    {
        "id": 1002,
        "number": 2,
        "title": "Ruffy versus Buggy, der Clown",
        "cover": "https://cdn.mp.de/op2.jpg",
        "year": 2001,
        "pages": 192,
        "edition": {
            "title": "One Piece",
            "sources": [],
        },
    },
]


# ---------------------------------------------------------------------------
# fetch_manga_metadata — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_success():
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(200, json=VOLUME_RESPONSE)

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)

    assert result is not None
    assert result["series_name"] == "One Piece"
    assert result["volume_title"] == "Das Abenteuer beginnt"
    assert result["volume_number"] == 1
    assert result["cover_url"] == "https://cdn.mp.de/op1.jpg"
    assert result["publication_year"] == 2001
    assert result["page_count"] == 200
    assert result["mp_volume_id"] == 1001
    assert result["mp_edition_id"] == 87
    assert result["authors"] == ["Eiichiro Oda"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_volume_2():
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(200, json=VOLUME_RESPONSE)

    result = await mangapassion.fetch_manga_metadata("One Piece", 2)

    assert result is not None
    assert result["volume_title"] == "Ruffy versus Buggy, der Clown"
    assert result["cover_url"] == "https://cdn.mp.de/op2.jpg"
    assert "authors" not in result  # no contributors in sources


# ---------------------------------------------------------------------------
# fetch_manga_metadata — no series_name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_manga_metadata_empty_series_name():
    result = await mangapassion.fetch_manga_metadata("", 1)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_manga_metadata_none_series_name():
    result = await mangapassion.fetch_manga_metadata(None, 1)
    assert result is None


# ---------------------------------------------------------------------------
# fetch_manga_metadata — no volume number
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_no_volume_number_no_title():
    """No volume_number and no volume_title → None after finding edition."""
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)

    result = await mangapassion.fetch_manga_metadata("One Piece", None)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_by_title():
    """When volume_number is None but volume_title is given, find by title match."""
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(200, json=VOLUME_RESPONSE)

    result = await mangapassion.fetch_manga_metadata(
        "One Piece", None, volume_title="Ruffy versus Buggy"
    )
    assert result is not None
    assert result["volume_title"] == "Ruffy versus Buggy, der Clown"
    assert result["volume_number"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_by_title_no_match():
    """Title below threshold returns None."""
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(200, json=VOLUME_RESPONSE)

    result = await mangapassion.fetch_manga_metadata(
        "One Piece", None, volume_title="Completely Unrelated Title That Wont Match"
    )
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_by_title_non_200():
    """Volumes endpoint non-200 when searching by title returns None."""
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(503)

    result = await mangapassion.fetch_manga_metadata(
        "One Piece", None, volume_title="Das Abenteuer beginnt"
    )
    assert result is None


# ---------------------------------------------------------------------------
# _search_best_edition — no editions found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_no_editions():
    respx.get(EDITIONS_URL).respond(200, json=[])

    result = await mangapassion.fetch_manga_metadata("Unknown Manga", 1)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_editions_non_200():
    respx.get(EDITIONS_URL).respond(503)

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_low_similarity():
    """Score below 0.5 threshold → no match."""
    respx.get(EDITIONS_URL).respond(200, json=[{"id": 1, "title": "Completely Different"}])

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_hydra_member_format():
    """API may return {"hydra:member": [...]} instead of a bare list."""
    respx.get(EDITIONS_URL).respond(200, json={"hydra:member": EDITIONS_RESPONSE})
    respx.get(_volumes_url(87)).respond(200, json=VOLUME_RESPONSE)

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)
    assert result is not None


# ---------------------------------------------------------------------------
# _fetch_volume — volume not found / non-200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_volume_not_found():
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(200, json=VOLUME_RESPONSE)

    result = await mangapassion.fetch_manga_metadata("One Piece", 99)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_volumes_non_200():
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(503)

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_volumes_hydra_member():
    respx.get(EDITIONS_URL).respond(200, json=EDITIONS_RESPONSE)
    respx.get(_volumes_url(87)).respond(200, json={"hydra:member": VOLUME_RESPONSE})

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)
    assert result is not None
    assert result["volume_title"] == "Das Abenteuer beginnt"


# ---------------------------------------------------------------------------
# Network errors — all non-fatal (return None)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_timeout():
    respx.get(EDITIONS_URL).mock(side_effect=httpx.TimeoutException("timed out"))

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_request_error():
    respx.get(EDITIONS_URL).mock(side_effect=httpx.RequestError("network"))

    result = await mangapassion.fetch_manga_metadata("One Piece", 1)
    assert result is None


# ---------------------------------------------------------------------------
# _parse_volume — author deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_manga_metadata_author_dedup():
    vol_with_dups = [{
        "id": 1,
        "number": 1,
        "title": "Vol 1",
        "cover": None,
        "year": 2000,
        "pages": 100,
        "edition": {
            "title": "Series",
            "sources": [
                {"contributors": [{"contributor": {"name": "Author A"}}]},
                {"contributors": [{"contributor": {"name": "Author A"}}, {"contributor": {"name": "Author B"}}]},
            ],
        },
    }]
    respx.get(EDITIONS_URL).respond(200, json=[{"id": 5, "title": "Series"}])
    respx.get(_volumes_url(5)).respond(200, json=vol_with_dups)

    result = await mangapassion.fetch_manga_metadata("Series", 1)
    assert result["authors"] == ["Author A", "Author B"]
