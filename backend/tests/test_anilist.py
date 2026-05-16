import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.anilist import fetch_anilist_by_title, _parse

MEDIA_RESPONSE = {
    "title": {"romaji": "Naruto", "english": "Naruto", "native": "ナルト"},
    "coverImage": {"large": "https://img.anilist.co/naruto_large.jpg", "medium": "https://img.anilist.co/naruto.jpg"},
    "startDate": {"year": 1999},
    "staff": {
        "edges": [
            {"role": "Story & Art", "node": {"name": {"full": "Masashi Kishimoto"}}},
        ]
    },
}


@pytest.mark.asyncio
async def test_empty_title_returns_none():
    result = await fetch_anilist_by_title("")
    assert result is None


@pytest.mark.asyncio
async def test_non_200_response_returns_none():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch("app.anilist.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_anilist_by_title("Naruto")
    assert result is None


@pytest.mark.asyncio
async def test_no_media_in_response_returns_none():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"Media": None}}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch("app.anilist.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_anilist_by_title("UnknownTitle")
    assert result is None


@pytest.mark.asyncio
async def test_timeout_returns_none():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    with patch("app.anilist.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_anilist_by_title("Naruto")
    assert result is None


@pytest.mark.asyncio
async def test_network_error_returns_none():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))
    with patch("app.anilist.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_anilist_by_title("Naruto")
    assert result is None


@pytest.mark.asyncio
async def test_successful_fetch_returns_parsed_data():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"Media": MEDIA_RESPONSE}}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch("app.anilist.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_anilist_by_title("Naruto")
    assert result is not None
    assert result["cover_url"] == "https://img.anilist.co/naruto_large.jpg"
    assert result["original_title"] == "ナルト"
    assert result["romanized_title"] == "Naruto"
    assert result["publication_year"] == 1999
    assert "Masashi Kishimoto" in result["authors"]


def test_parse_no_authors():
    media = {
        "title": {"romaji": "TestManga", "native": "テスト", "english": None},
        "coverImage": {"large": None, "medium": "https://img.anilist.co/test.jpg"},
        "startDate": {"year": 2020},
        "staff": {"edges": []},
    }
    result = _parse(media, "TestManga")
    assert result["cover_url"] == "https://img.anilist.co/test.jpg"
    assert "authors" not in result


def test_parse_deduplicates_authors():
    media = {
        "title": {"romaji": "Dup", "native": None, "english": None},
        "coverImage": {"large": "https://img.anilist.co/dup.jpg"},
        "startDate": None,
        "staff": {
            "edges": [
                {"role": "Art", "node": {"name": {"full": "Author One"}}},
                {"role": "Story", "node": {"name": {"full": "Author One"}}},
            ]
        },
    }
    result = _parse(media, "Dup")
    assert result["authors"].count("Author One") == 1
