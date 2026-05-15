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
