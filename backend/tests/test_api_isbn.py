import pytest
import respx
import httpx
from unittest.mock import patch, AsyncMock
from sqlalchemy.exc import SQLAlchemyError

from tests.conftest import create_user_and_login

GBOOKS = "https://www.googleapis.com/books/v1/volumes"
OL = "https://openlibrary.org/api/books"

GOOGLE_HIT = {
    "totalItems": 1,
    "items": [{
        "volumeInfo": {
            "title": "The Hobbit",
            "authors": ["Tolkien"],
            "publishedDate": "1937",
            "pageCount": 310,
            "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9780618002221"}],
        }
    }]
}

DNB_MANGA_HIT = {
    "title": "Naruto, Band 1",
    "authors": ["Kishimoto Masashi"],
    "media_type": "manga",
    "series_name": "Naruto",
    "volume_number": "1",
    "original_title": "ナルト",
    "demographic": "shounen",
    "page_count": 192,
    "description": "Ein junger Ninja...",
    "dnb_id": "123456789",
    "chapters": [
        {"order_index": 0, "chapter_number": "1", "title": "Naruto Uzumaki"},
    ],
    "language": "ger",
}


@pytest.mark.asyncio
@respx.mock
async def test_isbn_import_success(client):
    h = await create_user_and_login(client)
    respx.get(GBOOKS).respond(200, json=GOOGLE_HIT)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None):
        resp = await client.post("/import/isbn", json={"isbn": "9780618002221"}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "The Hobbit"
    assert data["source"] == "google"


@pytest.mark.asyncio
async def test_isbn_empty(client):
    h = await create_user_and_login(client)
    resp = await client.post("/import/isbn", json={"isbn": "   "}, headers=h)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


@pytest.mark.asyncio
@respx.mock
async def test_isbn_lookup_not_found(client):
    h = await create_user_and_login(client)
    respx.get(GBOOKS).respond(200, json={"totalItems": 0})
    respx.get(OL).respond(200, json={})
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None):
        resp = await client.post("/import/isbn", json={"isbn": "9780000000000"}, headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_isbn_unexpected_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.crud.parse_isbn_metadata", side_effect=RuntimeError("crash")):
        resp = await client.post("/import/isbn", json={"isbn": "9780618002221"}, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_isbn_httpx_request_error(client):
    """Covers the except httpx.RequestError branch in the import router."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None), \
         patch(
             "app.routers.import_isbn.crud.parse_isbn_metadata",
             side_effect=httpx.RequestError("network"),
         ):
        resp = await client.post("/import/isbn", json={"isbn": "9780618002221"}, headers=h)
    assert resp.status_code == 502


@pytest.mark.asyncio
@respx.mock
async def test_isbn_save_db_error(client):
    h = await create_user_and_login(client)
    respx.get(GBOOKS).respond(200, json=GOOGLE_HIT)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.crud.create_item", side_effect=SQLAlchemyError("db")):
        resp = await client.post("/import/isbn", json={"isbn": "9780618002221"}, headers=h)
    assert resp.status_code == 500
    assert "could not be saved" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# New: DNB-driven manga import
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_isbn_import_manga_creates_manga_volume(client):
    """DNB returns manga data → item.media_type=manga and MangaVolume row created."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=DNB_MANGA_HIT), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["media_type"] == "manga"
    assert data["source"] == "dnb"
    assert data["manga_meta"] is not None
    assert data["manga_meta"]["demographic"] == "shounen"
    assert len(data["manga_meta"]["chapters"]) == 1


@pytest.mark.asyncio
async def test_isbn_import_merges_dnb_and_google(client):
    """DNB wins for structured fields (media_type, demographic); Google fills cover_url."""
    h = await create_user_and_login(client)
    google_data = {
        "title": "Naruto 1",
        "authors": ["Kishimoto"],
        "cover_url": "http://example.com/cover.jpg",
        "media_type": "book",
    }
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=DNB_MANGA_HIT), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(google_data, "google")):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "dnb+google"
    assert data["media_type"] == "manga"  # DNB wins over Google's "book"
    assert data["manga_meta"] is not None
    assert data["manga_meta"]["demographic"] == "shounen"


@pytest.mark.asyncio
async def test_isbn_import_both_sources_fail(client):
    """Both DNB and Google/OL return nothing → 404."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")):
        resp = await client.post("/import/isbn", json={"isbn": "9780000000000"}, headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_isbn_manga_volume_db_error_nonfatal(client):
    """upsert_manga_volume failure is non-fatal: Item is still returned with 201."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=DNB_MANGA_HIT), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.crud.upsert_manga_volume",
               side_effect=SQLAlchemyError("db")):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["media_type"] == "manga"
    assert resp.json()["manga_meta"] is None  # not saved due to error
