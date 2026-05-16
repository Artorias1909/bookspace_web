import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from tests.conftest import create_user_and_login

ITEM_PAYLOAD = {"title": "Foundation", "authors": ["Asimov"], "page_count": 255}


async def _create_entry(client, headers):
    resp = await client.post("/user-items/", json={"item": ITEM_PAYLOAD, "status": "unread"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_user_item(client):
    h = await create_user_and_login(client)
    entry = await _create_entry(client, h)
    assert entry["item"]["title"] == "Foundation"
    assert entry["status"] == "unread"


@pytest.mark.asyncio
async def test_create_user_item_value_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.user_items.crud.create_user_item_data", side_effect=ValueError("bad")):
        resp = await client.post("/user-items/", json={"item": ITEM_PAYLOAD}, headers=h)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_user_item_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.user_items.crud.create_user_item_data", side_effect=SQLAlchemyError("db")):
        resp = await client.post("/user-items/", json={"item": ITEM_PAYLOAD}, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_list_user_items(client):
    h = await create_user_and_login(client)
    await _create_entry(client, h)
    resp = await client.get("/user-items/", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "items" in data


@pytest.mark.asyncio
async def test_list_user_items_pagination(client):
    h = await create_user_and_login(client)
    for _ in range(3):
        await _create_entry(client, h)
    resp = await client.get("/user-items/?page=1&page_size=2", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2


@pytest.mark.asyncio
async def test_list_user_items_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.user_items.crud.list_user_items", side_effect=SQLAlchemyError("db")):
        resp = await client.get("/user-items/", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_get_user_item(client):
    h = await create_user_and_login(client)
    entry = await _create_entry(client, h)
    resp = await client.get(f"/user-items/{entry['id']}", headers=h)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_user_item_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.get("/user-items/9999", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_item_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.user_items.crud.get_user_item", side_effect=SQLAlchemyError("db")):
        resp = await client.get("/user-items/1", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_user_item(client):
    h = await create_user_and_login(client)
    entry = await _create_entry(client, h)
    resp = await client.put(
        f"/user-items/{entry['id']}",
        json={"status": "reading", "current_page": 50},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reading"


@pytest.mark.asyncio
async def test_update_user_item_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.put("/user-items/9999", json={"status": "reading"}, headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_user_item_fetch_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.user_items.crud.get_user_item", side_effect=SQLAlchemyError("db")):
        resp = await client.put("/user-items/1", json={"status": "reading"}, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_user_item_save_db_error(client):
    h = await create_user_and_login(client)
    entry = await _create_entry(client, h)
    with patch("app.routers.user_items.crud.update_user_item_data", side_effect=SQLAlchemyError("db")):
        resp = await client.put(f"/user-items/{entry['id']}", json={"status": "reading"}, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_delete_user_item(client):
    h = await create_user_and_login(client)
    entry = await _create_entry(client, h)
    resp = await client.delete(f"/user-items/{entry['id']}", headers=h)
    assert resp.status_code == 204
    # Confirm it's gone
    get_resp = await client.get(f"/user-items/{entry['id']}", headers=h)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_item_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.delete("/user-items/9999", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_item_fetch_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.user_items.crud.get_user_item", side_effect=SQLAlchemyError("db")):
        resp = await client.delete("/user-items/1", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_delete_user_item_delete_db_error(client):
    h = await create_user_and_login(client)
    entry = await _create_entry(client, h)
    with patch("app.routers.user_items.crud.delete_user_item", side_effect=SQLAlchemyError("db")):
        resp = await client.delete(f"/user-items/{entry['id']}", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_list_user_items_status_filter(client):
    h = await create_user_and_login(client)
    await _create_entry(client, h)  # status=unread
    resp_reading = await client.post(
        "/user-items/", json={"item": ITEM_PAYLOAD, "status": "reading"}, headers=h
    )
    assert resp_reading.status_code == 201

    resp = await client.get("/user-items/?status=reading", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert all(item["status"] == "reading" for item in data["items"])


@pytest.mark.asyncio
async def test_create_user_item_duplicate_returns_409(client):
    """Adding the same item_id twice returns 409 Conflict."""
    h = await create_user_and_login(client)
    entry = await _create_entry(client, h)
    item_id = entry["item"]["id"]

    resp2 = await client.post("/user-items/", json={"item_id": item_id, "status": "reading"}, headers=h)
    assert resp2.status_code == 409
    assert "Bibliothek" in resp2.json()["detail"]
