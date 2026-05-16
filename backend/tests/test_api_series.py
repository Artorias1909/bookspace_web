import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from tests.conftest import create_user_and_login

SERIES_PAYLOAD = {"name": "Berserk", "type": "manga", "total_volumes": 41}
ITEM_PAYLOAD = {"title": "Berserk Vol 1", "authors": ["Miura"], "page_count": 240}


async def _create_series(client, headers, payload=None):
    resp = await client.post("/series/", json=payload or SERIES_PAYLOAD, headers=headers)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_series(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    assert s["name"] == "Berserk"


@pytest.mark.asyncio
async def test_create_series_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.create_series", side_effect=SQLAlchemyError("db")):
        resp = await client.post("/series/", json=SERIES_PAYLOAD, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_read_series_list(client):
    h = await create_user_and_login(client)
    await _create_series(client, h)
    resp = await client.get("/series/", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_read_series_list_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.list_series", side_effect=SQLAlchemyError("db")):
        resp = await client.get("/series/", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_get_series(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    resp = await client.get(f"/series/{s['id']}", headers=h)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_series_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.get("/series/9999", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_series_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.get_series", side_effect=SQLAlchemyError("db")):
        resp = await client.get("/series/1", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_series(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    resp = await client.put(
        f"/series/{s['id']}",
        json={"name": "Berserk Deluxe", "type": "manga", "total_volumes": 13},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Berserk Deluxe"


@pytest.mark.asyncio
async def test_update_series_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.put("/series/9999", json=SERIES_PAYLOAD, headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_series_fetch_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.get_series", side_effect=SQLAlchemyError("db")):
        resp = await client.put("/series/1", json=SERIES_PAYLOAD, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_series_save_db_error(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    with patch("app.routers.series.crud.get_series", return_value=type("S", (), {
        "name": "x", "type": "manga", "total_volumes": 1,
        "__class__": type("S", (), {})()
    })()) as _:
        pass
    # Patch the db.commit inside the router's update handler
    from unittest.mock import AsyncMock
    with patch("sqlalchemy.ext.asyncio.AsyncSession.commit", side_effect=SQLAlchemyError("db")):
        resp = await client.put(f"/series/{s['id']}", json=SERIES_PAYLOAD, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_assign_item_to_series(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    item_resp = await client.post("/items/", json=ITEM_PAYLOAD, headers=h)
    item_id = item_resp.json()["id"]
    resp = await client.post(
        f"/series/{s['id']}/assign/{item_id}?volume_number=1", headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["series_id"] == s["id"]


@pytest.mark.asyncio
async def test_assign_series_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.post("/series/9999/assign/1", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_item_not_found(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    resp = await client.post(f"/series/{s['id']}/assign/9999", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_series_fetch_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.get_series", side_effect=SQLAlchemyError("db")):
        resp = await client.post("/series/1/assign/1", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_assign_item_db_error(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    with patch("app.routers.series.crud.assign_item_to_series", side_effect=SQLAlchemyError("db")):
        resp = await client.post(f"/series/{s['id']}/assign/1", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_series_items(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    item_resp = await client.post("/items/", json=ITEM_PAYLOAD, headers=h)
    await client.post(f"/series/{s['id']}/assign/{item_resp.json()['id']}", headers=h)
    resp = await client.get(f"/series/{s['id']}/items", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_series_items_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.get("/series/9999/items", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_series_items_series_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.get_series", side_effect=SQLAlchemyError("db")):
        resp = await client.get("/series/1/items", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_series_items_list_db_error(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    with patch("app.routers.series.crud.list_series_items", side_effect=SQLAlchemyError("db")):
        resp = await client.get(f"/series/{s['id']}/items", headers=h)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# cover_url on series
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_series_with_cover_url(client):
    h = await create_user_and_login(client)
    payload = {**SERIES_PAYLOAD, "cover_url": "https://example.com/cover.jpg"}
    resp = await client.post("/series/", json=payload, headers=h)
    assert resp.status_code == 201
    assert resp.json()["cover_url"] == "https://example.com/cover.jpg"


@pytest.mark.asyncio
async def test_update_series_cover_url(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    resp = await client.put(
        f"/series/{s['id']}",
        json={**SERIES_PAYLOAD, "cover_url": "https://example.com/new.jpg"},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["cover_url"] == "https://example.com/new.jpg"


# ---------------------------------------------------------------------------
# Bulk series status update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_series_status_sets_all_entries(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    # Create two items in the series
    for vol in ("1", "2"):
        item_resp = await client.post("/items/", json={**ITEM_PAYLOAD, "title": f"Vol {vol}"}, headers=h)
        item_id = item_resp.json()["id"]
        await client.post(f"/series/{s['id']}/assign/{item_id}?volume_number={vol}", headers=h)
        await client.post("/user-items/", json={"item_id": item_id, "status": "unread"}, headers=h)

    resp = await client.patch(
        f"/series/{s['id']}/status",
        json={"status": "reading"},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2


@pytest.mark.asyncio
async def test_bulk_series_status_completed_sets_progress(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    item_resp = await client.post("/items/", json={**ITEM_PAYLOAD, "page_count": 240}, headers=h)
    item_id = item_resp.json()["id"]
    await client.post(f"/series/{s['id']}/assign/{item_id}?volume_number=1", headers=h)
    await client.post("/user-items/", json={"item_id": item_id, "status": "unread"}, headers=h)

    resp = await client.patch(f"/series/{s['id']}/status", json={"status": "completed"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1

    # Verify progress is 100% via list endpoint
    lib = await client.get("/user-items/", headers=h)
    entry = next(e for e in lib.json()["items"] if e["item"]["id"] == item_id)
    assert entry["progress_percent"] == 100.0
    assert entry["item"]["page_count"] == entry["current_page"]


@pytest.mark.asyncio
async def test_bulk_series_status_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.patch("/series/9999/status", json={"status": "reading"}, headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_series_status_invalid_status(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    resp = await client.patch(f"/series/{s['id']}/status", json={"status": "invalid"}, headers=h)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_series_status_fetch_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.get_series", side_effect=SQLAlchemyError("db")):
        resp = await client.patch("/series/1/status", json={"status": "reading"}, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_bulk_series_status_update_db_error(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    with patch("app.routers.series.crud.bulk_update_series_status", side_effect=SQLAlchemyError("db")):
        resp = await client.patch(f"/series/{s['id']}/status", json={"status": "reading"}, headers=h)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Delete series from library
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_series_from_library(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    # Add two items to library via the series
    for vol in ("1", "2"):
        item_resp = await client.post("/items/", json={**ITEM_PAYLOAD, "title": f"Vol {vol}"}, headers=h)
        item_id = item_resp.json()["id"]
        await client.post(f"/series/{s['id']}/assign/{item_id}?volume_number={vol}", headers=h)
        await client.post("/user-items/", json={"item_id": item_id, "status": "unread"}, headers=h)

    resp = await client.delete(f"/series/{s['id']}/library", headers=h)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    # Verify library is now empty for this series
    lib = await client.get("/user-items/", headers=h)
    assert lib.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_series_from_library_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.delete("/series/9999/library", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_series_from_library_fetch_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.series.crud.get_series", side_effect=SQLAlchemyError("db")):
        resp = await client.delete("/series/1/library", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_delete_series_from_library_delete_db_error(client):
    h = await create_user_and_login(client)
    s = await _create_series(client, h)
    with patch("app.routers.series.crud.delete_user_series_entries", side_effect=SQLAlchemyError("db")):
        resp = await client.delete(f"/series/{s['id']}/library", headers=h)
    assert resp.status_code == 500
