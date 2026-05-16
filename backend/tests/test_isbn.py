"""
Tests for parse_isbn_metadata — covers every branch:
Google success, Google no-results, Google 429/400/403/other,
Google timeout/connect/request errors, OL success, OL empty,
OL non-200, OL timeout/connect/request errors, both sources fail,
invalid ISBN inputs, unexpected exception.
"""
import pytest
import respx
import httpx
from unittest.mock import patch, AsyncMock

from app import crud

GBOOKS = "https://www.googleapis.com/books/v1/volumes"
OL = "https://openlibrary.org/api/books"

GOOGLE_HIT = {
    "totalItems": 1,
    "items": [{
        "volumeInfo": {
            "title": "Harry Potter",
            "authors": ["J.K. Rowling"],
            "publishedDate": "1997",
            "pageCount": 223,
            "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9780747532743"}],
        }
    }]
}

OL_HIT = {
    "ISBN:9780747532743": {
        "title": "Harry Potter OL",
        "authors": [{"name": "Rowling"}],
        "publish_date": "1997",
        "number_of_pages": 223,
        "identifiers": {"isbn_13": ["9780747532743"]},
        "cover": {"large": "http://covers.openlibrary.org/L.jpg"},
    }
}

VALID_ISBN = "9780747532743"


# ---------------------------------------------------------------------------
# Invalid ISBN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_isbn_empty_after_sanitize():
    with pytest.raises(ValueError, match="Invalid ISBN"):
        await crud.parse_isbn_metadata("ABC")


@pytest.mark.asyncio
async def test_isbn_wrong_length():
    with pytest.raises(ValueError, match="Invalid ISBN length"):
        await crud.parse_isbn_metadata("12345")


# ---------------------------------------------------------------------------
# Google success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_google_success():
    respx.get(GBOOKS).respond(200, json=GOOGLE_HIT)
    respx.get(OL).respond(200, json={})
    result, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "google"
    assert result["title"] == "Harry Potter"


@pytest.mark.asyncio
@respx.mock
async def test_google_success_with_api_key():
    with patch("app.crud.isbn.GOOGLE_BOOKS_API_KEY", "my-test-key"):
        respx.get(GBOOKS).respond(200, json=GOOGLE_HIT)
        respx.get(OL).respond(200, json={})
        result, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "google"


@pytest.mark.asyncio
@respx.mock
async def test_google_and_ol_merged():
    ol_with_series = {
        f"ISBN:{VALID_ISBN}": {
            "title": "Harry Potter",
            "authors": [{"name": "J.K. Rowling"}],
            "publish_date": "1997",
            "subjects": [{"name": "series:Harry Potter"}, {"name": "form:graphic novel"}],
            "subtitle": "The Philosopher's Stone",
        }
    }
    respx.get(GBOOKS).respond(200, json=GOOGLE_HIT)
    respx.get(OL).respond(200, json=ol_with_series)
    result, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "google+openlibrary"
    assert result["series_name"] == "Harry Potter"
    assert result["volume_title"] == "The Philosopher's Stone"


@pytest.mark.asyncio
@respx.mock
async def test_ol_cover_used_when_google_has_none():
    """OL cover fills in when Google returns no imageLinks."""
    google_no_cover = {
        "totalItems": 1,
        "items": [{"volumeInfo": {"title": "Harry Potter", "publishedDate": "1997"}}],
    }
    ol_with_cover = {
        f"ISBN:{VALID_ISBN}": {
            "title": "Harry Potter",
            "cover": {"large": "http://covers.ol.org/L.jpg"},
        }
    }
    respx.get(GBOOKS).respond(200, json=google_no_cover)
    respx.get(OL).respond(200, json=ol_with_cover)
    result, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "google+openlibrary"
    assert result["cover_url"] == "http://covers.ol.org/L.jpg"


# ---------------------------------------------------------------------------
# Google no results → OL success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_google_no_results_ol_success():
    respx.get(GBOOKS).respond(200, json={"totalItems": 0})
    respx.get(OL).respond(200, json=OL_HIT)
    result, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "openlibrary"
    assert result["title"] == "Harry Potter OL"


# ---------------------------------------------------------------------------
# Google 429 → OL success / both fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_google_rate_limited_ol_success():
    respx.get(GBOOKS).respond(429)
    respx.get(OL).respond(200, json=OL_HIT)
    result, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "openlibrary"


@pytest.mark.asyncio
@respx.mock
async def test_google_rate_limited_no_key_both_fail():
    respx.get(GBOOKS).respond(429)
    respx.get(OL).respond(200, json={})  # OL returns empty
    with pytest.raises(ValueError, match="daily quota"):
        await crud.parse_isbn_metadata(VALID_ISBN)


@pytest.mark.asyncio
@respx.mock
async def test_google_rate_limited_with_key_both_fail():
    with patch("app.crud.isbn.GOOGLE_BOOKS_API_KEY", "some-key"):
        respx.get(GBOOKS).respond(429)
        respx.get(OL).respond(200, json={})
        with pytest.raises(ValueError, match="API key quota"):
            await crud.parse_isbn_metadata(VALID_ISBN)


# ---------------------------------------------------------------------------
# Google 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_google_400_ol_success():
    respx.get(GBOOKS).respond(400, json={"error": {"message": "Bad request"}})
    respx.get(OL).respond(200, json=OL_HIT)
    result, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "openlibrary"


@pytest.mark.asyncio
@respx.mock
async def test_google_400_both_fail():
    respx.get(GBOOKS).respond(400, json={"error": {"message": "Bad"}})
    respx.get(OL).respond(200, json={})
    with pytest.raises(ValueError, match="Google Books"):
        await crud.parse_isbn_metadata(VALID_ISBN)


# ---------------------------------------------------------------------------
# Google 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_google_403_ol_success():
    respx.get(GBOOKS).respond(403)
    respx.get(OL).respond(200, json=OL_HIT)
    _, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "openlibrary"


@pytest.mark.asyncio
@respx.mock
async def test_google_403_both_fail():
    respx.get(GBOOKS).respond(403)
    respx.get(OL).respond(200, json={})
    with pytest.raises(ValueError, match="invalid or the Books API"):
        await crud.parse_isbn_metadata(VALID_ISBN)


# ---------------------------------------------------------------------------
# Google unexpected status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_google_unexpected_status_both_fail():
    respx.get(GBOOKS).respond(503)
    respx.get(OL).respond(200, json={})
    with pytest.raises(ValueError, match="HTTP 503"):
        await crud.parse_isbn_metadata(VALID_ISBN)


# ---------------------------------------------------------------------------
# Google network errors → OL success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_google_timeout_ol_success():
    respx.get(GBOOKS).mock(side_effect=httpx.TimeoutException("timed out"))
    respx.get(OL).respond(200, json=OL_HIT)
    _, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "openlibrary"


@pytest.mark.asyncio
@respx.mock
async def test_google_connect_error_ol_success():
    respx.get(GBOOKS).mock(side_effect=httpx.ConnectError("refused"))
    respx.get(OL).respond(200, json=OL_HIT)
    _, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "openlibrary"


@pytest.mark.asyncio
@respx.mock
async def test_google_request_error_ol_success():
    respx.get(GBOOKS).mock(side_effect=httpx.RequestError("generic"))
    respx.get(OL).respond(200, json=OL_HIT)
    _, source = await crud.parse_isbn_metadata(VALID_ISBN)
    assert source == "openlibrary"


# ---------------------------------------------------------------------------
# OL network errors (Google already failed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_ol_timeout_both_fail():
    respx.get(GBOOKS).respond(200, json={"totalItems": 0})
    respx.get(OL).mock(side_effect=httpx.TimeoutException("timeout"))
    with pytest.raises(ValueError, match="timed out"):
        await crud.parse_isbn_metadata(VALID_ISBN)


@pytest.mark.asyncio
@respx.mock
async def test_ol_connect_error_both_fail():
    respx.get(GBOOKS).respond(200, json={"totalItems": 0})
    respx.get(OL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ValueError, match="connect"):
        await crud.parse_isbn_metadata(VALID_ISBN)


@pytest.mark.asyncio
@respx.mock
async def test_ol_request_error_both_fail():
    respx.get(GBOOKS).respond(200, json={"totalItems": 0})
    respx.get(OL).mock(side_effect=httpx.RequestError("network"))
    with pytest.raises(ValueError, match="network"):
        await crud.parse_isbn_metadata(VALID_ISBN)


# ---------------------------------------------------------------------------
# OL non-200 status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_ol_non200_both_fail():
    respx.get(GBOOKS).respond(200, json={"totalItems": 0})
    respx.get(OL).respond(503)
    with pytest.raises(ValueError, match="HTTP 503"):
        await crud.parse_isbn_metadata(VALID_ISBN)


# ---------------------------------------------------------------------------
# Unexpected outer exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unexpected_exception():
    with patch("app.crud.isbn.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("boom"))
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ValueError, match="Unexpected error"):
            await crud.parse_isbn_metadata(VALID_ISBN)


# ---------------------------------------------------------------------------
# ISBN with dashes (sanitization)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_isbn_with_dashes():
    respx.get(GBOOKS).respond(200, json=GOOGLE_HIT)
    respx.get(OL).respond(200, json={})
    result, source = await crud.parse_isbn_metadata("978-0-747-53274-3")
    assert source == "google"


# ---------------------------------------------------------------------------
# Final fallback message includes manual entry hint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_error_message_includes_manual_hint():
    respx.get(GBOOKS).respond(200, json={"totalItems": 0})
    respx.get(OL).respond(200, json={})
    with pytest.raises(ValueError, match="manually"):
        await crud.parse_isbn_metadata(VALID_ISBN)
