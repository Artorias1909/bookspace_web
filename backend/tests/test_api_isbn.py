import pytest
import respx
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
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
    "publication_year": 2023,
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
    respx.get(OL).respond(200, json={})
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


def test_sanitize_isbn_strips_hyphens_and_spaces():
    """Regression: hyphens/spaces must be removed so '978-3551024374' == '9783551024374'."""
    from app.routers.import_isbn import _sanitize_isbn
    assert _sanitize_isbn("978-3-551-02437-4") == "9783551024374"
    assert _sanitize_isbn("978 3551024374") == "9783551024374"
    assert _sanitize_isbn("9783551024374") == "9783551024374"
    assert _sanitize_isbn("‏ 978-3551024374") == "9783551024374"  # invisible char + hyphen
    assert _sanitize_isbn("   ") == ""


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
    respx.get(OL).respond(200, json={})
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
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
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
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(google_data, "google")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
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
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None), \
         patch("app.routers.import_isbn.crud.upsert_manga_volume",
               side_effect=SQLAlchemyError("db")):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["media_type"] == "manga"
    assert resp.json()["manga_meta"] is None  # not saved due to error


@pytest.mark.asyncio
async def test_isbn_series_link_db_error_nonfatal(client):
    """assign_item_to_series failure is non-fatal: Item is still returned with 201."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=DNB_MANGA_HIT), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None), \
         patch("app.routers.import_isbn.crud.assign_item_to_series",
               side_effect=SQLAlchemyError("db")):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["media_type"] == "manga"


@pytest.mark.asyncio
async def test_isbn_anilist_enriches_cover(client):
    """AniList cover_url replaces whatever DNB left as None."""
    h = await create_user_and_login(client)
    anilist_data = {
        "cover_url": "https://img.anilist.co/naruto.jpg",
        "original_title": "ナルト",
        "romanized_title": "Naruto",
        "publication_year": 1999,
    }
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=DNB_MANGA_HIT), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=anilist_data), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["cover_url"] == "https://img.anilist.co/naruto.jpg"


@pytest.mark.asyncio
async def test_isbn_mangapassion_enriches_cover_and_title(client):
    """Manga-passion cover_url and volume_title override AniList/DNB values."""
    h = await create_user_and_login(client)
    mp_data = {
        "cover_url": "https://cdn.manga-passion.de/naruto1.jpg",
        "series_name": "Naruto",
        "volume_title": "Uzumaki Naruto",
        "publication_year": 2002,
        "page_count": 192,
        "mp_volume_id": 99,
        "mp_edition_id": 7,
    }
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=DNB_MANGA_HIT), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=mp_data):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["cover_url"] == "https://cdn.manga-passion.de/naruto1.jpg"
    assert data["volume_title"] == "Uzumaki Naruto"


@pytest.mark.asyncio
async def test_isbn_mangapassion_fills_gaps(client):
    """Manga-passion authors/page_count fill in when metadata has none."""
    h = await create_user_and_login(client)
    dnb_no_page = {**DNB_MANGA_HIT, "page_count": None, "authors": []}
    mp_data = {
        "cover_url": "https://cdn.mp.de/op1.jpg",
        "series_name": "Naruto",
        "volume_title": "Vol Title",
        "authors": ["Kishimoto Masashi"],
        "page_count": 192,
        "publication_year": 2002,
        "mp_volume_id": 1,
        "mp_edition_id": 5,
    }
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=dnb_no_page), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=mp_data):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["page_count"] == 192


@pytest.mark.asyncio
async def test_isbn_mangapassion_non_numeric_volume(client):
    """Non-numeric volume_number is handled gracefully (mp_vol_int becomes None)."""
    h = await create_user_and_login(client)
    dnb_special = {**DNB_MANGA_HIT, "volume_number": "Special Edition"}
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=dnb_special), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None) as mock_mp:
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    mock_mp.assert_called_once_with("Naruto", None, volume_title=None)


@pytest.mark.asyncio
async def test_isbn_mangapassion_fills_volume_number(client):
    """Manga-passion volume_number fills in when metadata has none."""
    h = await create_user_and_login(client)
    dnb_no_vol = {**DNB_MANGA_HIT, "volume_number": None, "series_name": "Naruto", "volume_title": "Uzumaki Naruto"}
    mp_data = {
        "cover_url": "https://cdn.mp.de/n1.jpg",
        "series_name": "Naruto",
        "volume_title": "Uzumaki Naruto",
        "volume_number": 1,
        "mp_volume_id": 10,
        "mp_edition_id": 3,
    }
    with patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=dnb_no_vol), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(None, "none")), \
         patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=mp_data):
        resp = await client.post("/import/isbn", json={"isbn": "9783551556714"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["volume_number"] == "1"


@pytest.mark.asyncio
async def test_isbn_returns_cached_existing_item(client):
    """Second import of same ISBN returns the existing item (source='cache')."""
    h = await create_user_and_login(client)
    from app import models

    fake_item = MagicMock(spec=models.Item)
    fake_item.id = 99
    fake_item.title = "Cached Book"
    fake_item.isbn = "9780618002221"
    fake_item.media_type = "book"
    fake_item.authors = ["Tolkien"]
    fake_item.publication_year = 1937
    fake_item.genre = "Fantasy"
    fake_item.page_count = 310
    fake_item.description = None
    fake_item.cover_url = None
    fake_item.cover_local_path = None
    fake_item.language = None
    fake_item.series_id = None
    fake_item.series = None
    fake_item.volume_number = None
    fake_item.volume_title = None
    fake_item.manga_meta = None
    fake_item.box_set_id = None
    fake_item.box_set = None

    with patch("app.routers.import_isbn.crud.get_item_by_isbn", return_value=fake_item), \
         patch("app.routers.import_isbn.crud.get_user_item_by_item_id", return_value=None):
        resp = await client.post("/import/isbn", json={"isbn": "9780618002221"}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "cache"
    assert data["title"] == "Cached Book"
    assert data["already_in_library"] is False


@pytest.mark.asyncio
async def test_isbn_cached_already_in_library(client):
    """Cached ISBN that's already in the user's library gets already_in_library=True."""
    h = await create_user_and_login(client)
    from app import models

    fake_item = MagicMock(spec=models.Item)
    fake_item.id = 99
    fake_item.title = "Cached Book"
    fake_item.isbn = "9780618002221"
    fake_item.media_type = "book"
    fake_item.authors = ["Tolkien"]
    fake_item.publication_year = 1937
    fake_item.genre = "Fantasy"
    fake_item.page_count = 310
    fake_item.description = None
    fake_item.cover_url = None
    fake_item.cover_local_path = None
    fake_item.language = None
    fake_item.series_id = None
    fake_item.series = None
    fake_item.volume_number = None
    fake_item.volume_title = None
    fake_item.manga_meta = None
    fake_item.box_set_id = None
    fake_item.box_set = None

    fake_entry = MagicMock(spec=models.UserItemData)
    with patch("app.routers.import_isbn.crud.get_item_by_isbn", return_value=fake_item), \
         patch("app.routers.import_isbn.crud.get_user_item_by_item_id", return_value=fake_entry):
        resp = await client.post("/import/isbn", json={"isbn": "9780618002221"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["already_in_library"] is True


# ---------------------------------------------------------------------------
# Sammelbox / BoxSet import
# ---------------------------------------------------------------------------

BOXSET_METADATA = {
    "title": "One Piece Sammelschuber 1: East Blue (inklusive Band 1-12)",
    "authors": ["Oda Eiichiro"],
    "media_type": "manga",
    "series_name": "One Piece",
    "cover_url": "https://example.com/op-box1.jpg",
    "publication_year": 2022,
    "page_count": None,
    "description": None,
    "language": "ger",
    "isbn": "978-3551024374",
    "volume_number": None,
    "volume_title": None,
    "genre": None,
}


@pytest.mark.asyncio
async def test_isbn_boxset_detected_and_created(client):
    """A Sammelschuber ISBN returns BoxSetImportResponse with all volumes."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.crud.get_item_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.crud.get_box_set_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(BOXSET_METADATA, "google")), \
         patch("app.routers.import_isbn.crud.find_series_by_name", return_value=None), \
         patch("app.routers.import_isbn.crud.find_or_create_series", new_callable=AsyncMock) as mock_series, \
         patch("app.routers.import_isbn.crud.create_box_set", new_callable=AsyncMock) as mock_box, \
         patch("app.routers.import_isbn.crud.find_or_create_volume_item", new_callable=AsyncMock) as mock_vol, \
         patch("app.routers.import_isbn._build_boxset_response", new_callable=AsyncMock) as mock_resp:
        from app import models, schemas
        fake_series = MagicMock(spec=models.Series)
        fake_series.id = 1
        fake_series.name = "One Piece"
        mock_series.return_value = fake_series

        fake_box = MagicMock(spec=models.BoxSet)
        fake_box.id = 10
        fake_box.isbn = "978-3551024374"
        fake_box.series_id = 1
        fake_box.name = "East Blue (inklusive Band 1-12)"
        fake_box.volume_from = 1
        fake_box.volume_to = 12
        fake_box.cover_url = "https://example.com/op-box1.jpg"
        fake_box.publication_year = 2022
        mock_box.return_value = fake_box

        fake_vol = MagicMock(spec=models.Item)
        fake_vol.id = 100
        mock_vol.return_value = fake_vol

        fake_response = schemas.BoxSetImportResponse(
            source="google",
            title="East Blue (inklusive Band 1-12)",
            cover_url="https://example.com/op-box1.jpg",
            authors=["Oda Eiichiro"],
            box_set=schemas.BoxSetRead(
                id=10, series_id=1, name="East Blue", isbn="978-3551024374",
                volume_from=1, volume_to=12, cover_url=None, publication_year=2022,
            ),
            box_volumes=[],
            volume_count=12,
        )
        mock_resp.return_value = fake_response

        resp = await client.post("/import/isbn", json={"isbn": "978-3551024374"}, headers=h)

    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "boxset"
    assert data["volume_count"] == 12
    assert mock_box.called
    assert mock_vol.call_count == 12


@pytest.mark.asyncio
async def test_isbn_boxset_db_error(client):
    """BoxSet DB error returns 500."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.crud.get_item_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.crud.get_box_set_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(BOXSET_METADATA, "google")), \
         patch("app.routers.import_isbn.crud.find_series_by_name", return_value=None), \
         patch("app.routers.import_isbn.crud.find_or_create_series", side_effect=SQLAlchemyError("db")):
        resp = await client.post("/import/isbn", json={"isbn": "978-3551024374"}, headers=h)
    assert resp.status_code == 500
    assert "could not be saved" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_isbn_boxset_cached(client):
    """Already-imported boxset ISBN returns cached BoxSetImportResponse."""
    h = await create_user_and_login(client)
    from app import models, schemas

    fake_box = MagicMock(spec=models.BoxSet)
    fake_box.id = 10
    fake_box.isbn = "978-3551024374"
    fake_box.series_id = 1
    fake_box.name = "East Blue"
    fake_box.volume_from = 1
    fake_box.volume_to = 12
    fake_box.cover_url = None
    fake_box.publication_year = 2022

    with patch("app.routers.import_isbn.crud.get_item_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.crud.get_box_set_by_isbn", return_value=fake_box), \
         patch("app.routers.import_isbn._build_boxset_response", new_callable=AsyncMock) as mock_resp:
        fake_response = schemas.BoxSetImportResponse(
            source="cache",
            title="East Blue",
            cover_url=None,
            authors=[],
            box_set=schemas.BoxSetRead(
                id=10, series_id=1, name="East Blue", isbn="978-3551024374",
                volume_from=1, volume_to=12, cover_url=None, publication_year=2022,
            ),
            box_volumes=[],
            volume_count=12,
        )
        mock_resp.return_value = fake_response
        resp = await client.post("/import/isbn", json={"isbn": "978-3551024374"}, headers=h)

    assert resp.status_code == 201
    assert resp.json()["source"] == "cache"
    assert resp.json()["type"] == "boxset"


# ---------------------------------------------------------------------------
# Direct integration tests for _enrich_boxset_volumes / _build_boxset_response
# These functions use a real DB session and are not reachable via the mocked
# API test fixtures above.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_boxset_response_loads_volumes_from_db(db_session):
    """_build_boxset_response without pre-loaded volume_items fetches them from DB."""
    from app import crud, schemas
    from app.routers.import_isbn import _build_boxset_response

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Toriko", type="manga"))
    box = await crud.create_box_set(db_session, series_id=series.id, name="Arc1", isbn="9783000000001", volume_from=1, volume_to=2)
    await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Toriko", volume_number=1, media_type="manga", authors=[], publication_year=None, box_set_id=box.id)
    await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Toriko", volume_number=2, media_type="manga", authors=[], publication_year=None, box_set_id=box.id)

    resp = await _build_boxset_response(db_session, box, source="cache")
    assert resp.type == "boxset"
    assert resp.volume_count == 2
    assert resp.already_in_library_ids == []


@pytest.mark.asyncio
async def test_build_boxset_response_marks_already_owned(db_session):
    """_build_boxset_response fills already_in_library_ids for volumes the user owns."""
    from app import crud, schemas
    from app.routers.import_isbn import _build_boxset_response

    user = await crud.create_user(db_session, schemas.UserCreate(username="yuki_boxset", password="pass1234"))
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Gintama", type="manga"))
    box = await crud.create_box_set(db_session, series_id=series.id, name="ArcG", isbn="9783000000002", volume_from=1, volume_to=2)
    vol1 = await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Gintama", volume_number=1, media_type="manga", authors=[], publication_year=None, box_set_id=box.id)
    await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Gintama", volume_number=2, media_type="manga", authors=[], publication_year=None, box_set_id=box.id)
    await crud.create_user_item_data(db_session, user.id, schemas.UserItemDataCreate(item_id=vol1.id))

    resp = await _build_boxset_response(db_session, box, source="cache", user_id=user.id)
    assert vol1.id in resp.already_in_library_ids
    assert len(resp.already_in_library_ids) == 1


@pytest.mark.asyncio
async def test_enrich_boxset_volumes_applies_mp_data(db_session):
    """_enrich_boxset_volumes updates cover_url / page_count from manga-passion."""
    from app import crud, schemas
    from app.routers.import_isbn import _enrich_boxset_volumes

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Spy x Family", type="manga"))
    vol = await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Spy x Family", volume_number=1, media_type="manga", authors=[], publication_year=None)

    mp_data = {"cover_url": "https://cdn.mp.de/spy1.jpg", "page_count": 192, "volume_title": "Operation Strix", "authors": ["Tatsuya Endo"], "publication_year": 2019}

    with patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=mp_data):
        enriched = await _enrich_boxset_volumes(db_session, "Spy x Family", "manga", [vol])

    assert enriched[0].cover_url == "https://cdn.mp.de/spy1.jpg"
    assert enriched[0].page_count == 192


@pytest.mark.asyncio
async def test_enrich_boxset_volumes_anilist_fallback(db_session):
    """When mp_data is None, AniList cover is used as fallback."""
    from app import crud, schemas
    from app.routers.import_isbn import _enrich_boxset_volumes

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Blue Period", type="manga"))
    vol = await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Blue Period", volume_number=1, media_type="manga", authors=[], publication_year=None)

    anilist_data = {"cover_url": "https://img.anilist.co/blue.jpg"}

    with patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=anilist_data), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
        enriched = await _enrich_boxset_volumes(db_session, "Blue Period", "manga", [vol])

    assert enriched[0].cover_url == "https://img.anilist.co/blue.jpg"


@pytest.mark.asyncio
async def test_enrich_boxset_volumes_no_changes(db_session):
    """When no enrichment data is found, items are returned unchanged."""
    from app import crud, schemas
    from app.routers.import_isbn import _enrich_boxset_volumes

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Dungeon Meshi", type="manga"))
    vol = await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Dungeon Meshi", volume_number=1, media_type="manga", authors=[], publication_year=None)

    with patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
        enriched = await _enrich_boxset_volumes(db_session, "Dungeon Meshi", "manga", [vol])

    assert enriched[0].cover_url is None


@pytest.mark.asyncio
async def test_enrich_boxset_volumes_non_manga_skips_anilist(db_session):
    """Non-manga media type skips the AniList lookup entirely."""
    from app import crud, schemas
    from app.routers.import_isbn import _enrich_boxset_volumes

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Sandman", type="comic"))
    vol = await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Sandman", volume_number=1, media_type="comic", authors=[], publication_year=None)

    with patch("app.routers.import_isbn.anilist.fetch_anilist_by_title") as mock_al, \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
        await _enrich_boxset_volumes(db_session, "Sandman", "comic", [vol])

    mock_al.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_boxset_volumes_anilist_exception_is_nonfatal(db_session):
    """AniList network error is caught and enrichment continues without cover."""
    from app import crud, schemas
    from app.routers.import_isbn import _enrich_boxset_volumes

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Chainsaw Man", type="manga"))
    vol = await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Chainsaw Man", volume_number=1, media_type="manga", authors=[], publication_year=None)

    with patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", side_effect=Exception("network")), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
        enriched = await _enrich_boxset_volumes(db_session, "Chainsaw Man", "manga", [vol])

    assert enriched[0].cover_url is None


@pytest.mark.asyncio
async def test_enrich_boxset_volumes_mp_exception_is_nonfatal(db_session):
    """Manga-passion exception inside _fetch_mp is caught; volume returned without data."""
    from app import crud, schemas
    from app.routers.import_isbn import _enrich_boxset_volumes

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Jujutsu Kaisen", type="manga"))
    vol = await crud.find_or_create_volume_item(db_session, series_id=series.id, series_name="Jujutsu Kaisen", volume_number=1, media_type="manga", authors=[], publication_year=None)

    with patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", side_effect=Exception("timeout")):
        enriched = await _enrich_boxset_volumes(db_session, "Jujutsu Kaisen", "manga", [vol])

    assert enriched[0].cover_url is None


@pytest.mark.asyncio
async def test_enrich_boxset_volumes_non_digit_volume_number(db_session):
    """Volume with non-digit volume_number triggers the _none() fallback path."""
    from app import crud, schemas
    from app.routers.import_isbn import _enrich_boxset_volumes
    from app import models

    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Special Series", type="manga"))
    item = await crud.create_item(db_session, schemas.ItemCreate(
        title="Special Edition", media_type="manga", series_id=series.id, volume_number="Special",
    ))

    with patch("app.routers.import_isbn.anilist.fetch_anilist_by_title", return_value=None), \
         patch("app.routers.import_isbn.mangapassion.fetch_manga_metadata", return_value=None):
        enriched = await _enrich_boxset_volumes(db_session, "Special Series", "manga", [item])

    assert enriched[0].volume_number == "Special"


@pytest.mark.asyncio
@respx.mock
async def test_handle_boxset_import_enrich_exception_nonfatal(client):
    """_handle_boxset_import catches _enrich_boxset_volumes exceptions (non-fatal)."""
    h = await create_user_and_login(client)
    with patch("app.routers.import_isbn.crud.get_item_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.crud.get_box_set_by_isbn", return_value=None), \
         patch("app.routers.import_isbn.dnb.fetch_dnb_by_isbn", return_value=None), \
         patch("app.routers.import_isbn._fetch_google_or_ol", return_value=(BOXSET_METADATA, "google")), \
         patch("app.routers.import_isbn.crud.find_series_by_name", return_value=None), \
         patch("app.routers.import_isbn.crud.find_or_create_series", new_callable=AsyncMock) as mock_series, \
         patch("app.routers.import_isbn.crud.create_box_set", new_callable=AsyncMock) as mock_box, \
         patch("app.routers.import_isbn.crud.find_or_create_volume_item", new_callable=AsyncMock) as mock_vol, \
         patch("app.routers.import_isbn._enrich_boxset_volumes", side_effect=Exception("enrichment crash")), \
         patch("app.routers.import_isbn._build_boxset_response", new_callable=AsyncMock) as mock_resp:
        from app import models, schemas
        fake_series = MagicMock(spec=models.Series)
        fake_series.id = 1
        fake_series.name = "One Piece"
        mock_series.return_value = fake_series

        fake_box = MagicMock(spec=models.BoxSet)
        fake_box.id = 10
        fake_box.isbn = "978-3551024374"
        fake_box.series_id = 1
        fake_box.name = "East Blue"
        fake_box.volume_from = 1
        fake_box.volume_to = 12
        fake_box.cover_url = None
        fake_box.publication_year = 2022
        mock_box.return_value = fake_box

        fake_vol = MagicMock(spec=models.Item)
        fake_vol.id = 100
        mock_vol.return_value = fake_vol

        fake_response = schemas.BoxSetImportResponse(
            source="google", title="East Blue", cover_url=None, authors=[],
            box_set=schemas.BoxSetRead(id=10, series_id=1, name="East Blue",
                isbn="978-3551024374", volume_from=1, volume_to=12, cover_url=None, publication_year=2022),
            box_volumes=[], volume_count=12,
        )
        mock_resp.return_value = fake_response

        resp = await client.post("/import/isbn", json={"isbn": "978-3551024374"}, headers=h)

    assert resp.status_code == 201
    assert resp.json()["type"] == "boxset"
