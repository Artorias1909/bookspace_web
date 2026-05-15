import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from tests.conftest import create_user_and_login

ITEM_PAYLOAD = {"title": "Dune", "authors": ["Frank Herbert"], "page_count": 688}


@pytest.mark.asyncio
async def test_create_item(client):
    h = await create_user_and_login(client)
    resp = await client.post("/items/", json=ITEM_PAYLOAD, headers=h)
    assert resp.status_code == 201
    assert resp.json()["title"] == "Dune"


@pytest.mark.asyncio
async def test_create_item_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.items.crud.create_item", side_effect=SQLAlchemyError("db")):
        resp = await client.post("/items/", json=ITEM_PAYLOAD, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_read_item(client):
    h = await create_user_and_login(client)
    created = (await client.post("/items/", json=ITEM_PAYLOAD, headers=h)).json()
    resp = await client.get(f"/items/{created['id']}", headers=h)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_item_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.get("/items/9999", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_read_item_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.items.crud.get_item", side_effect=SQLAlchemyError("db")):
        resp = await client.get("/items/1", headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_item(client):
    h = await create_user_and_login(client)
    created = (await client.post("/items/", json=ITEM_PAYLOAD, headers=h)).json()
    resp = await client.put(f"/items/{created['id']}", json={**ITEM_PAYLOAD, "title": "Dune Messiah"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Dune Messiah"


@pytest.mark.asyncio
async def test_update_item_not_found(client):
    h = await create_user_and_login(client)
    resp = await client.put("/items/9999", json=ITEM_PAYLOAD, headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_item_fetch_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.items.crud.get_item", side_effect=SQLAlchemyError("db")):
        resp = await client.put("/items/1", json=ITEM_PAYLOAD, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_item_save_db_error(client):
    h = await create_user_and_login(client)
    created = (await client.post("/items/", json=ITEM_PAYLOAD, headers=h)).json()
    with patch("app.routers.items.crud.update_item", side_effect=SQLAlchemyError("db")):
        resp = await client.put(f"/items/{created['id']}", json=ITEM_PAYLOAD, headers=h)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_search_items(client):
    h = await create_user_and_login(client)
    await client.post("/items/", json=ITEM_PAYLOAD, headers=h)
    resp = await client.get("/items/search?q=Dune", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_search_items_no_query(client):
    h = await create_user_and_login(client)
    resp = await client.get("/items/search", headers=h)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_search_items_db_error(client):
    h = await create_user_and_login(client)
    with patch("app.routers.items.crud.search_items", side_effect=SQLAlchemyError("db")):
        resp = await client.get("/items/search?q=x", headers=h)
    assert resp.status_code == 500
