import pytest
from pydantic import ValidationError
from app import schemas


def test_token_defaults():
    t = schemas.Token(access_token="abc")
    assert t.token_type == "bearer"


def test_user_create_too_short_username():
    with pytest.raises(ValidationError):
        schemas.UserCreate(username="ab", password="password123")


def test_user_create_too_short_password():
    with pytest.raises(ValidationError):
        schemas.UserCreate(username="valid", password="short")


def test_user_create_valid():
    u = schemas.UserCreate(username="validuser", password="validpass")
    assert u.username == "validuser"


def test_authors_validator_string_input():
    item = schemas.ItemCreate(title="Book", authors="Alice, Bob, Charlie")
    assert item.authors == ["Alice", "Bob", "Charlie"]


def test_authors_validator_string_strips_blanks():
    item = schemas.ItemCreate(title="Book", authors=" Alice ,  Bob ")
    assert item.authors == ["Alice", "Bob"]


def test_authors_validator_list_passthrough():
    item = schemas.ItemCreate(title="Book", authors=["Alice", "Bob"])
    assert item.authors == ["Alice", "Bob"]


def test_authors_validator_empty_string():
    item = schemas.ItemCreate(title="Book", authors="")
    assert item.authors == []


def test_series_base_invalid_type():
    with pytest.raises(ValidationError):
        schemas.SeriesCreate(name="X", type="novel")


def test_series_base_valid_types():
    for t in ("book", "manga", "comic"):
        s = schemas.SeriesCreate(name="S", type=t)
        assert s.type == t


def test_user_item_data_invalid_status():
    with pytest.raises(ValidationError):
        schemas.UserItemDataCreate(status="done")


def test_user_item_data_valid_statuses():
    for s in ("unread", "reading", "completed", "owned", "wishlist"):
        d = schemas.UserItemDataCreate(status=s)
        assert d.status == s


def test_paged_response_build_with_items():
    items = ["a", "b", "c"]
    resp = schemas.PagedResponse.build(items=items, total=30, page=2, page_size=10)
    assert resp.items == items
    assert resp.total == 30
    assert resp.page == 2
    assert resp.page_size == 10
    assert resp.pages == 3


def test_paged_response_build_zero_total():
    resp = schemas.PagedResponse.build(items=[], total=0, page=1, page_size=24)
    assert resp.pages == 1


def test_isbn_import_request():
    r = schemas.ISBNImportRequest(isbn="978-3-551-55167-2")
    assert r.isbn == "978-3-551-55167-2"


def test_item_base_valid_media_types():
    for mt in ("book", "manga", "comic"):
        item = schemas.ItemCreate(title="T", media_type=mt)
        assert item.media_type == mt


def test_item_base_invalid_media_type():
    with pytest.raises(ValidationError):
        schemas.ItemCreate(title="T", media_type="novel")


def test_chapter_entry_create_valid():
    ch = schemas.ChapterEntryCreate(order_index=0, chapter_number="1", title="Opening")
    assert ch.order_index == 0
    assert ch.chapter_number == "1"
    assert ch.title == "Opening"


def test_chapter_entry_create_minimal():
    ch = schemas.ChapterEntryCreate(order_index=5)
    assert ch.order_index == 5
    assert ch.chapter_number is None
    assert ch.title is None


def test_manga_volume_valid_demographics():
    for d in ("shounen", "shoujo", "seinen", "josei", "kodomomuke"):
        mv = schemas.MangaVolumeCreate(demographic=d)
        assert mv.demographic == d


def test_manga_volume_invalid_demographic():
    with pytest.raises(ValidationError):
        schemas.MangaVolumeCreate(demographic="children")


def test_manga_volume_valid_reading_directions():
    for rd in ("rtl", "ltr"):
        mv = schemas.MangaVolumeCreate(reading_direction=rd)
        assert mv.reading_direction == rd


def test_manga_volume_invalid_reading_direction():
    with pytest.raises(ValidationError):
        schemas.MangaVolumeCreate(reading_direction="diagonal")


def test_manga_volume_create_chapters_default_empty():
    mv = schemas.MangaVolumeCreate()
    assert mv.chapters == []


def test_manga_volume_update_chapters_default_none():
    mv = schemas.MangaVolumeUpdate()
    assert mv.chapters is None


def test_manga_volume_create_with_chapters():
    mv = schemas.MangaVolumeCreate(
        chapters=[schemas.ChapterEntryCreate(order_index=0, title="Ch1")]
    )
    assert len(mv.chapters) == 1
    assert mv.chapters[0].title == "Ch1"
