from datetime import datetime
from math import ceil
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------

class SeriesBase(BaseModel):
    name: str
    type: str = Field(..., pattern="^(book|manga|comic)$")
    total_volumes: Optional[int] = None


class SeriesCreate(SeriesBase):
    pass


class SeriesRead(SeriesBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# Chapters (manga-specific)
# ---------------------------------------------------------------------------

class ChapterEntryBase(BaseModel):
    order_index: int
    chapter_number: Optional[str] = None
    title: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None


class ChapterEntryCreate(ChapterEntryBase):
    pass


class ChapterEntryRead(ChapterEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# MangaVolume (manga-specific metadata, 1:1 with Item)
# ---------------------------------------------------------------------------

class MangaVolumeBase(BaseModel):
    original_title: Optional[str] = None
    romanized_title: Optional[str] = None
    demographic: Optional[str] = Field(
        None,
        pattern="^(shounen|shoujo|seinen|josei|kodomomuke)$",
    )
    reading_direction: str = Field("rtl", pattern="^(rtl|ltr)$")
    dnb_id: Optional[str] = None
    animexx_id: Optional[str] = None


class MangaVolumeCreate(MangaVolumeBase):
    chapters: List[ChapterEntryCreate] = Field(default_factory=list)


class MangaVolumeUpdate(MangaVolumeBase):
    # When provided, replaces the entire chapter list
    chapters: Optional[List[ChapterEntryCreate]] = None


class MangaVolumeRead(MangaVolumeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapters: List[ChapterEntryRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class ItemBase(BaseModel):
    media_type: str = Field("book", pattern="^(book|manga|comic)$")
    title: str
    authors: List[str] = Field(default_factory=list)
    publication_year: Optional[int] = None
    genre: Optional[str] = None
    page_count: Optional[int] = None
    description: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    cover_local_path: Optional[str] = None
    language: Optional[str] = None
    series_id: Optional[int] = None
    volume_number: Optional[str] = None
    volume_title: Optional[str] = None

    @field_validator("authors", mode="before")
    @classmethod
    def authors_to_list(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


class ItemCreate(ItemBase):
    pass


class ItemUpdate(ItemBase):
    pass


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    series: Optional[SeriesRead] = None
    manga_meta: Optional[MangaVolumeRead] = None


# ---------------------------------------------------------------------------
# User item data
# ---------------------------------------------------------------------------

class UserItemDataBase(BaseModel):
    status: Optional[str] = Field(None, pattern="^(unread|reading|completed|owned|wishlist)$")
    current_page: Optional[int] = None


class UserItemDataCreate(UserItemDataBase):
    item_id: Optional[int] = None
    item: Optional[ItemCreate] = None


class UserItemDataUpdate(UserItemDataBase):
    pass


class UserItemDataRead(UserItemDataBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item: ItemRead
    progress_percent: float
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PagedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: List[T], total: int, page: int, page_size: int) -> "PagedResponse[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 1,
        )


# ---------------------------------------------------------------------------
# ISBN import
# ---------------------------------------------------------------------------

class ISBNImportRequest(BaseModel):
    isbn: str


class ISBNImportResponse(ItemRead):
    source: str
    raw_metadata: Optional[dict] = None
