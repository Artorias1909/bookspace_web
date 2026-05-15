"""Tests for pure (non-DB) functions in crud.py."""
import pytest
from app import crud


# ---------------------------------------------------------------------------
# calculate_progress
# ---------------------------------------------------------------------------

def test_progress_zero_pages():
    assert crud.calculate_progress(50, 0) == 0.0


def test_progress_none_pages():
    assert crud.calculate_progress(50, None) == 0.0


def test_progress_normal():
    assert crud.calculate_progress(50, 200) == 25.0


def test_progress_capped_at_100():
    assert crud.calculate_progress(999, 100) == 100.0


def test_progress_exact_100():
    assert crud.calculate_progress(100, 100) == 100.0


# ---------------------------------------------------------------------------
# extract_series_fields
# ---------------------------------------------------------------------------

def test_extract_vol_pattern():
    result = crud.extract_series_fields("My Series Vol. 3", None)
    assert result["volume_number"] == "3"
    assert result["volume_title"] == "My Series Vol. 3"
    assert result["series_id"] is None


def test_extract_vol_no_dot():
    result = crud.extract_series_fields("Attack on Titan Vol 5", "")
    assert result["volume_number"] == "5"


def test_extract_volume_long():
    result = crud.extract_series_fields("Great Series Volume 12", None)
    assert result["volume_number"] == "12"


def test_extract_band_pattern():
    result = crud.extract_series_fields("Dragon Ball Band 7", None)
    assert result["volume_number"] == "7"


def test_extract_hash_pattern():
    result = crud.extract_series_fields("Naruto #4", None)
    assert result["volume_number"] == "4"


def test_extract_no_match():
    result = crud.extract_series_fields("A Standalone Book", None)
    assert result == {"series_id": None, "volume_number": None, "volume_title": None}


def test_extract_uses_subtitle():
    result = crud.extract_series_fields("My Series", "Vol. 2")
    assert result["volume_number"] == "2"


# ---------------------------------------------------------------------------
# get_isbn_from_info
# ---------------------------------------------------------------------------

def test_get_isbn_13():
    info = {"industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567890"}]}
    assert crud.get_isbn_from_info(info) == "9781234567890"


def test_get_isbn_10_fallback():
    info = {"industryIdentifiers": [{"type": "ISBN_10", "identifier": "1234567890"}]}
    assert crud.get_isbn_from_info(info) == "1234567890"


def test_get_isbn_no_identifier():
    assert crud.get_isbn_from_info({}) is None


def test_get_isbn_wrong_type():
    info = {"industryIdentifiers": [{"type": "OTHER", "identifier": "999"}]}
    assert crud.get_isbn_from_info(info) is None


# ---------------------------------------------------------------------------
# parse_google_book
# ---------------------------------------------------------------------------

FULL_GOOGLE_ITEM = {
    "volumeInfo": {
        "title": "The Hobbit",
        "authors": ["J.R.R. Tolkien"],
        "publishedDate": "1937-09-21",
        "pageCount": 310,
        "categories": ["Fantasy", "Fiction"],
        "description": "A tale of Bilbo Baggins.",
        "language": "en",
        "imageLinks": {"thumbnail": "http://example.com/thumb.jpg", "large": "http://example.com/large.jpg"},
        "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9780618002221"}],
    }
}


def test_parse_google_book_full():
    result = crud.parse_google_book(FULL_GOOGLE_ITEM)
    assert result["title"] == "The Hobbit"
    assert result["authors"] == ["J.R.R. Tolkien"]
    assert result["publication_year"] == 1937
    assert result["page_count"] == 310
    assert result["genre"] == "Fantasy, Fiction"
    assert result["language"] == "en"
    assert result["cover_url"] == "http://example.com/large.jpg"
    assert result["isbn"] == "9780618002221"


def test_parse_google_book_missing_fields():
    result = crud.parse_google_book({"volumeInfo": {"title": "Bare"}})
    assert result["title"] == "Bare"
    assert result["authors"] == []
    assert result["publication_year"] is None
    assert result["genre"] is None
    assert result["cover_url"] is None


def test_parse_google_book_bad_date():
    item = {"volumeInfo": {"title": "X", "publishedDate": "not-a-year"}}
    result = crud.parse_google_book(item)
    assert result["publication_year"] is None


def test_parse_google_book_genre_capped_at_3():
    item = {"volumeInfo": {"title": "X", "categories": ["A", "B", "C", "D"]}}
    result = crud.parse_google_book(item)
    assert result["genre"] == "A, B, C"


# ---------------------------------------------------------------------------
# parse_open_library_api
# ---------------------------------------------------------------------------

FULL_OL_API_DATA = {
    "title": "Fellowship of the Ring",
    "authors": [{"name": "Tolkien"}, {"name": "Extra"}],
    "publish_date": "1954",
    "number_of_pages": 423,
    "identifiers": {"isbn_13": ["9780007117116"], "isbn_10": ["0007117116"]},
    "cover": {"large": "http://covers.ol.org/L.jpg", "medium": "http://covers.ol.org/M.jpg"},
    "subjects": [{"name": "Fantasy"}, {"name": "Epic"}, {"name": "Adventure"}, {"name": "Extra"}],
    "excerpts": [{"text": "In a hole in the ground..."}],
}


def test_parse_ol_api_full():
    result = crud.parse_open_library_api(FULL_OL_API_DATA, "9780007117116")
    assert result["title"] == "Fellowship of the Ring"
    assert result["authors"] == ["Tolkien", "Extra"]
    assert result["publication_year"] == 1954
    assert result["page_count"] == 423
    assert result["isbn"] == "9780007117116"
    assert result["cover_url"] == "http://covers.ol.org/L.jpg"
    assert result["genre"] == "Fantasy, Epic, Adventure"
    assert result["description"] == "In a hole in the ground..."


def test_parse_ol_api_isbn_fallback():
    result = crud.parse_open_library_api({"title": "X"}, "FALLBACK")
    assert result["isbn"] == "FALLBACK"


def test_parse_ol_api_isbn_10_fallback():
    data = {"title": "X", "identifiers": {"isbn_10": ["0123456789"]}}
    result = crud.parse_open_library_api(data)
    assert result["isbn"] == "0123456789"


def test_parse_ol_api_missing_fields():
    result = crud.parse_open_library_api({})
    assert result["title"] == ""
    assert result["authors"] == []
    assert result["publication_year"] is None
    assert result["cover_url"] is None
    assert result["description"] is None


def test_parse_ol_api_bad_date():
    result = crud.parse_open_library_api({"title": "X", "publish_date": "bad"})
    assert result["publication_year"] is None


def test_parse_ol_api_medium_cover_fallback():
    data = {"title": "X", "cover": {"medium": "http://example.com/M.jpg"}}
    result = crud.parse_open_library_api(data)
    assert result["cover_url"] == "http://example.com/M.jpg"


def test_parse_ol_api_no_excerpts():
    result = crud.parse_open_library_api({"title": "X", "excerpts": []})
    assert result["description"] is None


# ---------------------------------------------------------------------------
# parse_open_library (legacy)
# ---------------------------------------------------------------------------

def test_parse_open_library_legacy_full():
    data = {
        "title": "Legacy Book",
        "authors": [{"name": "Auth One"}, {"key": "/authors/1"}],
        "publish_date": "2001",
        "number_of_pages": 200,
        "notes": "Some notes",
        "isbn_13": ["9781234567890"],
        "covers": [12345],
        "languages": [{"key": "/languages/eng"}],
    }
    result = crud.parse_open_library(data)
    assert result["title"] == "Legacy Book"
    assert result["authors"] == ["Auth One"]
    assert result["publication_year"] == 2001
    assert result["description"] == "Some notes"
    assert result["isbn"] == "9781234567890"
    assert "12345" in result["cover_url"]
    assert result["language"] == "eng"


def test_parse_open_library_legacy_isbn_10_fallback():
    data = {"title": "X", "isbn_10": ["0123456789"]}
    result = crud.parse_open_library(data)
    assert result["isbn"] == "0123456789"


def test_parse_open_library_legacy_notes_not_str():
    data = {"title": "X", "notes": {"value": "complex"}}
    result = crud.parse_open_library(data)
    assert result["description"] is None


def test_parse_open_library_legacy_bad_date():
    data = {"title": "X", "publish_date": "not-a-year"}
    result = crud.parse_open_library(data)
    assert result["publication_year"] is None


def test_parse_open_library_legacy_no_covers():
    data = {"title": "X"}
    result = crud.parse_open_library(data)
    assert result["cover_url"] is None
    assert result["language"] is None
