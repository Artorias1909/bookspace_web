"""Integration tests for the manga metadata router (GET/PUT /items/{id}/meta)."""
import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from tests.conftest import create_user_and_login

ITEM_PAYLOAD = {"title": "Naruto", "authors": ["Kishimoto"], "media_type": "manga"}

MANGA_META = {
    "original_title": "ナルト",
    "demographic": "shounen",
    "reading_direction": "rtl",
    "chapters": [
        {"order_index": 0, "chapter_number": "697", "title": "Naruto und Sasuke"},
        {"order_index": 1, "chapter_number": "698", "title": "Das Ende"},
    ],
}


async def _create_item(client, headers, payload=None):
    resp = await client.post("/items/", json=payload or ITEM_PAYLOAD, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _create_and_own_item(client, headers, payload=None):
    """Create an item and add it to the user's library."""
    item = await _create_item(client, headers, payload)
    await client.post("/user-items/", json={"item_id": item["id"], "status": "unread"}, headers=headers)
    return item


# ---------------------------------------------------------------------------
# GET /items/{item_id}/meta
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_manga_meta_no_manga_data_is_404(client):
    """Item exists but has no MangaVolume row yet."""
    h = await create_user_and_login(client)
    item = await _create_item(client, h)
    resp = await client.get(f"/items/{item['id']}/meta", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_manga_meta_nonexistent_item_is_404(client):
    h = await create_user_and_login(client)
    resp = await client.get("/items/9999/meta", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_manga_meta_requires_auth(client):
    resp = await client.get("/items/1/meta")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_manga_meta_success(client):
    h = await create_user_and_login(client)
    item = await _create_and_own_item(client, h)
    await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h)
    resp = await client.get(f"/items/{item['id']}/meta", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["demographic"] == "shounen"
    assert data["original_title"] == "ナルト"
    assert data["reading_direction"] == "rtl"
    assert len(data["chapters"]) == 2


# ---------------------------------------------------------------------------
# PUT /items/{item_id}/meta
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_manga_meta_creates(client):
    h = await create_user_and_login(client)
    item = await _create_and_own_item(client, h)
    resp = await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["demographic"] == "shounen"
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["chapter_number"] == "697"
    assert data["chapters"][0]["title"] == "Naruto und Sasuke"


@pytest.mark.asyncio
async def test_upsert_manga_meta_chapters_ordered(client):
    h = await create_user_and_login(client)
    item = await _create_and_own_item(client, h)
    resp = await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h)
    chapters = resp.json()["chapters"]
    indices = [ch["order_index"] for ch in chapters]
    assert indices == sorted(indices)


@pytest.mark.asyncio
async def test_upsert_manga_meta_update_replaces(client):
    """A second PUT replaces demographic and clears chapters."""
    h = await create_user_and_login(client)
    item = await _create_and_own_item(client, h)
    await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h)
    update = {**MANGA_META, "demographic": "seinen", "chapters": []}
    resp = await client.put(f"/items/{item['id']}/meta", json=update, headers=h)
    assert resp.status_code == 200
    assert resp.json()["demographic"] == "seinen"
    assert resp.json()["chapters"] == []


@pytest.mark.asyncio
async def test_upsert_manga_meta_no_chapters_field(client):
    """PUT without chapters key leaves existing chapters untouched
    (chapters=None means 'do not replace')."""
    h = await create_user_and_login(client)
    item = await _create_and_own_item(client, h)
    await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h)
    # Update only demographic, omit chapters
    resp = await client.put(
        f"/items/{item['id']}/meta",
        json={"demographic": "seinen"},
        headers=h,
    )
    assert resp.status_code == 200
    # Chapters should still be present from the first PUT
    assert len(resp.json()["chapters"]) == 2


@pytest.mark.asyncio
async def test_upsert_manga_meta_item_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.put("/items/9999/meta", json=MANGA_META, headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upsert_manga_meta_forbidden_when_not_in_library(client):
    """User B cannot update manga metadata for an item only User A owns."""
    h_a = await create_user_and_login(client, username="manga_user_a", password="pass1234")
    h_b = await create_user_and_login(client, username="manga_user_b", password="pass1234")
    item = await _create_and_own_item(client, h_a)
    resp = await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h_b)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upsert_manga_meta_db_error(client):
    h = await create_user_and_login(client)
    item = await _create_and_own_item(client, h)
    with patch("app.routers.manga.crud.upsert_manga_volume", side_effect=SQLAlchemyError("db")):
        resp = await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_upsert_manga_meta_invalid_demographic(client):
    h = await create_user_and_login(client)
    item = await _create_item(client, h)
    bad = {**MANGA_META, "demographic": "children"}
    resp = await client.put(f"/items/{item['id']}/meta", json=bad, headers=h)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upsert_manga_meta_invalid_reading_direction(client):
    h = await create_user_and_login(client)
    item = await _create_item(client, h)
    bad = {**MANGA_META, "reading_direction": "diagonal"}
    resp = await client.put(f"/items/{item['id']}/meta", json=bad, headers=h)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upsert_manga_meta_requires_auth(client):
    resp = await client.put("/items/1/meta", json=MANGA_META)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Item response includes manga_meta after import
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_item_read_includes_manga_meta(client):
    """After PUT /meta, GET /items/{id} also exposes manga_meta."""
    h = await create_user_and_login(client)
    item = await _create_and_own_item(client, h)
    await client.put(f"/items/{item['id']}/meta", json=MANGA_META, headers=h)
    resp = await client.get(f"/items/{item['id']}", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["manga_meta"] is not None
    assert data["manga_meta"]["demographic"] == "shounen"
