"""Integration tests for async CRUD functions against in-memory SQLite."""
import pytest
from app import crud, schemas


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_item_create(**kwargs):
    defaults = {"title": "Test Book", "authors": ["Author A"], "page_count": 300}
    return schemas.ItemCreate(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_get_user(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="alice", password="pass1234"))
    assert user.id is not None
    found = await crud.get_user_by_username(db_session, "alice")
    assert found.id == user.id


@pytest.mark.asyncio
async def test_get_user_not_found(db_session):
    assert await crud.get_user_by_username(db_session, "nobody") is None


@pytest.mark.asyncio
async def test_authenticate_user_success(db_session):
    await crud.create_user(db_session, schemas.UserCreate(username="bob", password="secret99"))
    user = await crud.authenticate_user(db_session, "bob", "secret99")
    assert user is not None


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db_session):
    await crud.create_user(db_session, schemas.UserCreate(username="carol", password="secret99"))
    assert await crud.authenticate_user(db_session, "carol", "wrong") is None


@pytest.mark.asyncio
async def test_authenticate_user_unknown(db_session):
    assert await crud.authenticate_user(db_session, "ghost", "pw") is None


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_get_series(db_session):
    s = await crud.create_series(db_session, schemas.SeriesCreate(name="My Series", type="manga"))
    assert s.id is not None
    found = await crud.get_series(db_session, s.id)
    assert found.name == "My Series"


@pytest.mark.asyncio
async def test_get_series_not_found(db_session):
    assert await crud.get_series(db_session, 9999) is None


@pytest.mark.asyncio
async def test_find_or_create_series_creates_new(db_session):
    s = await crud.find_or_create_series(db_session, "One Piece", "manga")
    assert s.id is not None
    assert s.name == "One Piece"


@pytest.mark.asyncio
async def test_find_or_create_series_returns_existing(db_session):
    first = await crud.find_or_create_series(db_session, "Bleach", "manga")
    second = await crud.find_or_create_series(db_session, "BLEACH", "manga")
    assert first.id == second.id


@pytest.mark.asyncio
async def test_find_series_by_name_found(db_session):
    await crud.create_series(db_session, schemas.SeriesCreate(name="Fairy Tail", type="manga"))
    found = await crud.find_series_by_name(db_session, "Fairy Tail")
    assert found is not None
    assert found.name == "Fairy Tail"


@pytest.mark.asyncio
async def test_find_series_by_name_not_found(db_session):
    assert await crud.find_series_by_name(db_session, "Does Not Exist") is None


@pytest.mark.asyncio
async def test_find_series_by_name_prefers_manga(db_session):
    await crud.create_series(db_session, schemas.SeriesCreate(name="Twin Peaks", type="book"))
    manga = await crud.create_series(db_session, schemas.SeriesCreate(name="Twin Peaks", type="manga"))
    found = await crud.find_series_by_name(db_session, "Twin Peaks")
    assert found.id == manga.id


@pytest.mark.asyncio
async def test_list_series(db_session):
    await crud.create_series(db_session, schemas.SeriesCreate(name="A", type="book"))
    await crud.create_series(db_session, schemas.SeriesCreate(name="B", type="comic"))
    rows = await crud.list_series(db_session)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_get_item(db_session):
    item = await crud.create_item(db_session, make_item_create())
    assert item.id is not None
    found = await crud.get_item(db_session, item.id)
    assert found.title == "Test Book"


@pytest.mark.asyncio
async def test_get_item_not_found(db_session):
    assert await crud.get_item(db_session, 9999) is None


@pytest.mark.asyncio
async def test_update_item(db_session):
    item = await crud.create_item(db_session, make_item_create())
    updated = await crud.update_item(
        db_session, item, schemas.ItemUpdate(title="Updated", authors=["Auth B"])
    )
    assert updated.title == "Updated"


@pytest.mark.asyncio
async def test_assign_item_to_series(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="S", type="manga"))
    item = await crud.create_item(db_session, make_item_create())
    result = await crud.assign_item_to_series(db_session, item.id, series.id, volume_number="1")
    assert result.series_id == series.id
    assert result.volume_number == "1"


@pytest.mark.asyncio
async def test_assign_item_not_found(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="S", type="manga"))
    result = await crud.assign_item_to_series(db_session, 9999, series.id)
    assert result is None


@pytest.mark.asyncio
async def test_assign_item_no_volume(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="S", type="book"))
    item = await crud.create_item(db_session, make_item_create())
    result = await crud.assign_item_to_series(db_session, item.id, series.id)
    assert result.series_id == series.id
    assert result.volume_number is None


@pytest.mark.asyncio
async def test_list_series_items(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="S", type="manga"))
    item = await crud.create_item(db_session, make_item_create())
    await crud.assign_item_to_series(db_session, item.id, series.id, "1")
    items = await crud.list_series_items(db_session, series.id)
    assert len(items) == 1


# ---------------------------------------------------------------------------
# UserItemData
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_user_item_with_new_item(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="dave", password="pass1234"))
    entry = await crud.create_user_item_data(
        db_session, user.id,
        schemas.UserItemDataCreate(item=make_item_create(), status="reading", current_page=50),
    )
    assert entry.status == "reading"
    assert entry.item.title == "Test Book"


@pytest.mark.asyncio
async def test_create_user_item_with_item_id(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="eve", password="pass1234"))
    item = await crud.create_item(db_session, make_item_create())
    entry = await crud.create_user_item_data(
        db_session, user.id,
        schemas.UserItemDataCreate(item_id=item.id),
    )
    assert entry.item_id == item.id


@pytest.mark.asyncio
async def test_create_user_item_item_id_not_found(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="frank", password="pass1234"))
    with pytest.raises(ValueError, match="not found"):
        await crud.create_user_item_data(
            db_session, user.id, schemas.UserItemDataCreate(item_id=9999)
        )


@pytest.mark.asyncio
async def test_create_user_item_no_item(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="grace", password="pass1234"))
    with pytest.raises(ValueError, match="required"):
        await crud.create_user_item_data(
            db_session, user.id, schemas.UserItemDataCreate()
        )


@pytest.mark.asyncio
async def test_get_user_item(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="hal", password="pass1234"))
    entry = await crud.create_user_item_data(
        db_session, user.id, schemas.UserItemDataCreate(item=make_item_create())
    )
    found = await crud.get_user_item(db_session, entry.id, user.id)
    assert found.id == entry.id


@pytest.mark.asyncio
async def test_get_user_item_not_found(db_session):
    assert await crud.get_user_item(db_session, 9999, 1) is None


@pytest.mark.asyncio
async def test_update_user_item(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="iris", password="pass1234"))
    entry = await crud.create_user_item_data(
        db_session, user.id, schemas.UserItemDataCreate(item=make_item_create())
    )
    fresh = await crud.get_user_item(db_session, entry.id, user.id)
    updated = await crud.update_user_item_data(
        db_session, fresh, schemas.UserItemDataUpdate(status="reading", current_page=100)
    )
    assert updated.status == "reading"
    assert updated.current_page == 100


@pytest.mark.asyncio
async def test_update_user_item_clamps_negative_page(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="jack", password="pass1234"))
    entry = await crud.create_user_item_data(
        db_session, user.id, schemas.UserItemDataCreate(item=make_item_create())
    )
    fresh = await crud.get_user_item(db_session, entry.id, user.id)
    updated = await crud.update_user_item_data(
        db_session, fresh, schemas.UserItemDataUpdate(current_page=-10)
    )
    assert updated.current_page == 0


@pytest.mark.asyncio
async def test_list_user_items_all_sort_options(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="kate", password="pass1234"))
    for i in range(3):
        await crud.create_user_item_data(
            db_session, user.id,
            schemas.UserItemDataCreate(
                item=schemas.ItemCreate(
                    title=f"Book {i}", authors=[f"Author {i}"], publication_year=2000 + i, page_count=100
                )
            ),
        )
    for sort_by in ("title", "author", "publication_year", "status"):
        for sort_dir in ("asc", "desc"):
            rows = await crud.list_user_items(db_session, user.id, sort_by=sort_by, sort_dir=sort_dir)
            assert len(rows) == 3


@pytest.mark.asyncio
async def test_list_user_items_with_query(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="leo", password="pass1234"))
    await crud.create_user_item_data(
        db_session, user.id, schemas.UserItemDataCreate(item=make_item_create(title="Unique Title"))
    )
    await crud.create_user_item_data(
        db_session, user.id, schemas.UserItemDataCreate(item=make_item_create(title="Other Book"))
    )
    rows = await crud.list_user_items(db_session, user.id, q="Unique")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_count_user_items(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="mia", password="pass1234"))
    for _ in range(5):
        await crud.create_user_item_data(
            db_session, user.id, schemas.UserItemDataCreate(item=make_item_create())
        )
    total = await crud.count_user_items(db_session, user.id)
    assert total == 5


@pytest.mark.asyncio
async def test_count_user_items_with_query(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="nina", password="pass1234"))
    await crud.create_user_item_data(
        db_session, user.id, schemas.UserItemDataCreate(item=make_item_create(title="Needle"))
    )
    await crud.create_user_item_data(
        db_session, user.id, schemas.UserItemDataCreate(item=make_item_create(title="Haystack"))
    )
    assert await crud.count_user_items(db_session, user.id, q="Needle") == 1


@pytest.mark.asyncio
async def test_list_user_items_with_status_filter(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="oscar", password="pass1234"))
    await crud.create_user_item_data(
        db_session, user.id,
        schemas.UserItemDataCreate(item=make_item_create(title="Reading Book"), status="reading"),
    )
    await crud.create_user_item_data(
        db_session, user.id,
        schemas.UserItemDataCreate(item=make_item_create(title="Unread Book"), status="unread"),
    )
    rows = await crud.list_user_items(db_session, user.id, status="reading")
    assert len(rows) == 1
    assert rows[0].status == "reading"


@pytest.mark.asyncio
async def test_count_user_items_with_status_filter(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="peter", password="pass1234"))
    for _ in range(3):
        await crud.create_user_item_data(
            db_session, user.id,
            schemas.UserItemDataCreate(item=make_item_create(), status="completed"),
        )
    await crud.create_user_item_data(
        db_session, user.id,
        schemas.UserItemDataCreate(item=make_item_create(), status="reading"),
    )
    assert await crud.count_user_items(db_session, user.id, status="completed") == 3
    assert await crud.count_user_items(db_session, user.id, status="reading") == 1


# ---------------------------------------------------------------------------
# MangaVolume CRUD
# ---------------------------------------------------------------------------

def make_manga_create(**kwargs):
    defaults = {
        "original_title": "ナルト",
        "demographic": "shounen",
        "reading_direction": "rtl",
        "chapters": [],
    }
    return schemas.MangaVolumeCreate(**{**defaults, **kwargs})


@pytest.mark.asyncio
async def test_get_manga_volume_not_found(db_session):
    assert await crud.get_manga_volume(db_session, 9999) is None


@pytest.mark.asyncio
async def test_get_manga_volume_found(db_session):
    item = await crud.create_item(db_session, make_item_create(media_type="manga"))
    await crud.upsert_manga_volume(db_session, item.id, make_manga_create())
    found = await crud.get_manga_volume(db_session, item.id)
    assert found is not None
    assert found.item_id == item.id


@pytest.mark.asyncio
async def test_upsert_manga_volume_creates(db_session):
    item = await crud.create_item(db_session, make_item_create(media_type="manga"))
    manga = await crud.upsert_manga_volume(db_session, item.id, make_manga_create())
    assert manga is not None
    assert manga.item_id == item.id
    assert manga.demographic == "shounen"
    assert manga.original_title == "ナルト"


@pytest.mark.asyncio
async def test_upsert_manga_volume_with_chapters(db_session):
    item = await crud.create_item(db_session, make_item_create(media_type="manga"))
    chapters = [
        schemas.ChapterEntryCreate(order_index=0, chapter_number="1", title="Ch1"),
        schemas.ChapterEntryCreate(order_index=1, chapter_number="2", title="Ch2"),
    ]
    manga = await crud.upsert_manga_volume(db_session, item.id, make_manga_create(chapters=chapters))
    assert len(manga.chapters) == 2
    assert manga.chapters[0].chapter_number == "1"


@pytest.mark.asyncio
async def test_upsert_manga_volume_updates_scalars(db_session):
    item = await crud.create_item(db_session, make_item_create(media_type="manga"))
    await crud.upsert_manga_volume(db_session, item.id, make_manga_create())
    updated = await crud.upsert_manga_volume(
        db_session, item.id,
        schemas.MangaVolumeCreate(demographic="seinen", original_title="ナルト"),
    )
    assert updated.demographic == "seinen"


@pytest.mark.asyncio
async def test_upsert_manga_volume_replaces_chapters(db_session):
    item = await crud.create_item(db_session, make_item_create(media_type="manga"))
    first_chapters = [schemas.ChapterEntryCreate(order_index=0, title="Old")]
    await crud.upsert_manga_volume(db_session, item.id, make_manga_create(chapters=first_chapters))
    new_chapters = [
        schemas.ChapterEntryCreate(order_index=0, title="New1"),
        schemas.ChapterEntryCreate(order_index=1, title="New2"),
    ]
    updated = await crud.upsert_manga_volume(db_session, item.id, make_manga_create(chapters=new_chapters))
    assert len(updated.chapters) == 2
    assert updated.chapters[0].title == "New1"


@pytest.mark.asyncio
async def test_upsert_manga_volume_none_chapters_preserves(db_session):
    item = await crud.create_item(db_session, make_item_create(media_type="manga"))
    chapters = [schemas.ChapterEntryCreate(order_index=0, title="Keep")]
    await crud.upsert_manga_volume(db_session, item.id, make_manga_create(chapters=chapters))
    # MangaVolumeUpdate has chapters=None by default — existing chapters must be preserved
    updated = await crud.upsert_manga_volume(
        db_session, item.id,
        schemas.MangaVolumeUpdate(demographic="josei"),
    )
    assert len(updated.chapters) == 1
    assert updated.chapters[0].title == "Keep"
    assert updated.demographic == "josei"


# ---------------------------------------------------------------------------
# BoxSet CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_box_set(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="One Piece", type="manga"))
    box = await crud.create_box_set(
        db_session,
        series_id=series.id,
        name="East Blue",
        isbn="978-3551024374",
        volume_from=1,
        volume_to=12,
        cover_url="https://example.com/cover.jpg",
        publication_year=2022,
    )
    assert box.id is not None
    assert box.volume_from == 1
    assert box.volume_to == 12
    assert box.isbn == "978-3551024374"


@pytest.mark.asyncio
async def test_get_box_set_by_isbn_found(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Naruto", type="manga"))
    await crud.create_box_set(db_session, series_id=series.id, name="Arc1", isbn="9783551234567", volume_from=1, volume_to=5)
    found = await crud.get_box_set_by_isbn(db_session, "9783551234567")
    assert found is not None
    assert found.name == "Arc1"


@pytest.mark.asyncio
async def test_get_box_set_by_isbn_not_found(db_session):
    assert await crud.get_box_set_by_isbn(db_session, "0000000000000") is None


@pytest.mark.asyncio
async def test_find_or_create_volume_item_creates_placeholder(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Bleach", type="manga"))
    item = await crud.find_or_create_volume_item(
        db_session,
        series_id=series.id,
        series_name="Bleach",
        volume_number=3,
        media_type="manga",
        authors=["Tite Kubo"],
        publication_year=2002,
    )
    assert item.id is not None
    assert item.volume_number == "3"
    assert item.series_id == series.id


@pytest.mark.asyncio
async def test_find_or_create_volume_item_returns_existing(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Dragon Ball", type="manga"))
    first = await crud.find_or_create_volume_item(
        db_session, series_id=series.id, series_name="Dragon Ball",
        volume_number=1, media_type="manga", authors=[], publication_year=None,
    )
    second = await crud.find_or_create_volume_item(
        db_session, series_id=series.id, series_name="Dragon Ball",
        volume_number=1, media_type="manga", authors=[], publication_year=None,
    )
    assert first.id == second.id


@pytest.mark.asyncio
async def test_find_or_create_volume_item_updates_box_set_id(db_session):
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Hunter x Hunter", type="manga"))
    box = await crud.create_box_set(
        db_session, series_id=series.id, name="Arc", isbn="9783551999001",
        volume_from=1, volume_to=3,
    )
    existing = await crud.find_or_create_volume_item(
        db_session, series_id=series.id, series_name="Hunter x Hunter",
        volume_number=1, media_type="manga", authors=[], publication_year=None,
    )
    assert existing.box_set_id is None
    updated = await crud.find_or_create_volume_item(
        db_session, series_id=series.id, series_name="Hunter x Hunter",
        volume_number=1, media_type="manga", authors=[], publication_year=None,
        box_set_id=box.id,
    )
    assert updated.id == existing.id
    assert updated.box_set_id == box.id


# ---------------------------------------------------------------------------
# get_user_item_by_item_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_item_by_item_id_found(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="quentin", password="pass1234"))
    item = await crud.create_item(db_session, make_item_create(title="Dune"))
    entry = await crud.create_user_item_data(db_session, user.id, schemas.UserItemDataCreate(item_id=item.id))
    found = await crud.get_user_item_by_item_id(db_session, user.id, item.id)
    assert found is not None
    assert found.id == entry.id


@pytest.mark.asyncio
async def test_get_user_item_by_item_id_not_found(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="rachel", password="pass1234"))
    assert await crud.get_user_item_by_item_id(db_session, user.id, 9999) is None


@pytest.mark.asyncio
async def test_create_user_item_data_duplicate_raises(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="samuel", password="pass1234"))
    item = await crud.create_item(db_session, make_item_create(title="The Road"))
    await crud.create_user_item_data(db_session, user.id, schemas.UserItemDataCreate(item_id=item.id))
    with pytest.raises(ValueError, match="already_in_library"):
        await crud.create_user_item_data(db_session, user.id, schemas.UserItemDataCreate(item_id=item.id))


# ---------------------------------------------------------------------------
# delete_user_series_entries / bulk_update_series_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_user_series_entries(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="tina", password="pass1234"))
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Attack on Titan", type="manga"))
    for i in range(3):
        item = await crud.create_item(db_session, make_item_create(title=f"AoT {i}", series_id=series.id))
        await crud.assign_item_to_series(db_session, item.id, series.id, str(i))
        await crud.create_user_item_data(db_session, user.id, schemas.UserItemDataCreate(item_id=item.id))
    count = await crud.delete_user_series_entries(db_session, user.id, series.id)
    assert count == 3
    total = await crud.count_user_items(db_session, user.id)
    assert total == 0


@pytest.mark.asyncio
async def test_delete_user_series_entries_only_affects_user(db_session):
    user_a = await crud.create_user(db_session, schemas.UserCreate(username="uma", password="pass1234"))
    user_b = await crud.create_user(db_session, schemas.UserCreate(username="victor", password="pass1234"))
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Vinland Saga", type="manga"))
    item = await crud.create_item(db_session, make_item_create(title="VS 1"))
    await crud.assign_item_to_series(db_session, item.id, series.id, "1")
    await crud.create_user_item_data(db_session, user_a.id, schemas.UserItemDataCreate(item_id=item.id))
    await crud.create_user_item_data(db_session, user_b.id, schemas.UserItemDataCreate(item_id=item.id))
    count = await crud.delete_user_series_entries(db_session, user_a.id, series.id)
    assert count == 1
    assert await crud.count_user_items(db_session, user_b.id) == 1


@pytest.mark.asyncio
async def test_bulk_update_series_status(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="wendy", password="pass1234"))
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="Berserk", type="manga"))
    for i in range(2):
        item = await crud.create_item(db_session, make_item_create(title=f"Berserk {i}"))
        await crud.assign_item_to_series(db_session, item.id, series.id, str(i))
        await crud.create_user_item_data(db_session, user.id, schemas.UserItemDataCreate(item_id=item.id, status="unread"))
    count = await crud.bulk_update_series_status(db_session, user.id, series.id, "reading")
    assert count == 2
    rows = await crud.list_user_items(db_session, user.id)
    assert all(r.status == "reading" for r in rows)


@pytest.mark.asyncio
async def test_bulk_update_series_status_completed(db_session):
    user = await crud.create_user(db_session, schemas.UserCreate(username="xavier", password="pass1234"))
    series = await crud.create_series(db_session, schemas.SeriesCreate(name="FMA", type="manga"))
    item = await crud.create_item(db_session, make_item_create(title="FMA 1", page_count=200))
    await crud.assign_item_to_series(db_session, item.id, series.id, "1")
    await crud.create_user_item_data(db_session, user.id, schemas.UserItemDataCreate(item_id=item.id))
    count = await crud.bulk_update_series_status(db_session, user.id, series.id, "completed")
    assert count == 1
    rows = await crud.list_user_items(db_session, user.id)
    assert rows[0].status == "completed"
