"""Pydantic request/response schemas for validation, serialization, and OpenAPI documentation."""
from datetime import datetime
from math import ceil
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class Token(BaseModel):
    """JWT bearer token returned after successful login."""

    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    """Shared username field with length constraints (3–128 characters)."""

    username: str = Field(..., min_length=3, max_length=128)


class UserCreate(UserBase):
    """Registration payload: username + password meeting minimum strength requirements."""

    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Require at least one letter and one digit in the password."""
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserRead(UserBase):
    """User representation returned by the API; never includes the password hash."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------

class SeriesBase(BaseModel):
    """Shared series fields; type must be one of: book, manga, comic."""

    name: str
    type: str = Field(..., pattern="^(book|manga|comic)$")
    total_volumes: Optional[int] = None
    cover_url: Optional[str] = None


class SeriesCreate(SeriesBase):
    """Payload for creating a new series."""


class SeriesRead(SeriesBase):
    """Series as returned by the API, including the generated primary key."""
    model_config = ConfigDict(from_attributes=True)

    id: int


class SeriesStatusUpdate(BaseModel):
    """Payload to bulk-set the reading status for all volumes of a series."""

    status: str = Field(..., pattern="^(unread|reading|completed|owned|wishlist)$")


class BulkUpdateResult(BaseModel):
    """Number of library entries affected by a bulk series operation."""

    updated: int


class BoxSetRead(BaseModel):
    """Collector box (Sammelschuber) as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    series_id: Optional[int] = None
    name: Optional[str] = None
    isbn: Optional[str] = None
    volume_from: int
    volume_to: int
    cover_url: Optional[str] = None
    publication_year: Optional[int] = None


# ---------------------------------------------------------------------------
# Chapters (manga-specific)
# ---------------------------------------------------------------------------

class ChapterEntryBase(BaseModel):
    """A single chapter within a manga volume; order_index controls display order."""

    order_index: int
    chapter_number: Optional[str] = None
    title: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None


class ChapterEntryCreate(ChapterEntryBase):
    """Payload for creating a chapter entry within a MangaVolume."""


class ChapterEntryRead(ChapterEntryBase):
    """Chapter entry as returned by the API, including the generated primary key."""
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# MangaVolume (manga-specific metadata, 1:1 with Item)
# ---------------------------------------------------------------------------

class MangaVolumeBase(BaseModel):
    """Manga-specific metadata shared across create, update, and read schemas."""

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
    """Payload for creating or replacing MangaVolume metadata; chapters list is written in full."""

    chapters: List[ChapterEntryCreate] = Field(default_factory=list)


class MangaVolumeUpdate(MangaVolumeBase):
    """Partial update payload; when chapters is provided it replaces the entire chapter list."""

    # When provided, replaces the entire chapter list
    chapters: Optional[List[ChapterEntryCreate]] = None


class MangaVolumeRead(MangaVolumeBase):
    """MangaVolume as returned by the API, including chapters ordered by order_index."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapters: List[ChapterEntryRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class ItemBase(BaseModel):
    """Core item fields shared across create, update, and read schemas."""

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
    box_set_id: Optional[int] = None

    @field_validator("authors", mode="before")
    @classmethod
    def authors_to_list(cls, v):
        """Coerce a comma-separated author string into a list; lists pass through unchanged."""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


class ItemCreate(ItemBase):
    """Payload for creating a new catalog item."""


class ItemUpdate(ItemBase):
    """Payload for fully replacing an existing catalog item's metadata."""


class ItemRead(ItemBase):
    """Item as returned by the API, including nested series, manga_meta, and box_set."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    series: Optional[SeriesRead] = None
    manga_meta: Optional[MangaVolumeRead] = None
    box_set: Optional[BoxSetRead] = None


# ---------------------------------------------------------------------------
# User item data
# ---------------------------------------------------------------------------

class UserItemDataBase(BaseModel):
    """Shared mutable reading-state fields (status and current page)."""

    status: Optional[str] = Field(None, pattern="^(unread|reading|completed|owned|wishlist)$")
    current_page: Optional[int] = None


class UserItemDataCreate(UserItemDataBase):
    """Add an item to a user's library — supply either item_id (existing) or item (new)."""

    item_id: Optional[int] = None
    item: Optional[ItemCreate] = None


class UserItemDataUpdate(UserItemDataBase):
    """Payload for updating reading status or current page of a library entry."""


class UserItemDataRead(UserItemDataBase):
    """Library entry as returned by the API, including the full nested item and progress."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    item: ItemRead
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def progress_percent(self) -> float:
        """Reading progress [0–100] derived from current_page and item.page_count."""
        page_count = self.item.page_count if self.item else None
        current = self.current_page or 0
        if not page_count or page_count <= 0:
            return 0.0
        return round(min(current / page_count * 100.0, 100.0), 2)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PagedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper with total count and page metadata."""

    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: List[T], total: int, page: int, page_size: int) -> "PagedResponse[T]":
        """Compute page count and wrap items in a PagedResponse.

        Args:
            items: The slice of results for this page.
            total: Total number of matching records across all pages.
            page: Current 1-based page number.
            page_size: Number of items per page.
        """
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
    """ISBN to look up; non-digit characters (spaces, hyphens, invisible Unicode) are stripped by the handler."""

    isbn: str


class ISBNImportResponse(ItemRead):
    """Item returned after a successful ISBN import; includes source provenance and library status."""

    type: Literal["item"] = "item"
    source: str
    raw_metadata: Optional[dict] = None
    already_in_library: bool = False


class BoxSetImportResponse(BaseModel):
    """Returned when the scanned ISBN is a collector box (Sammelschuber/Sammelbox)."""
    type: Literal["boxset"] = "boxset"
    source: str
    title: str                        # arc name or boxset title for display
    cover_url: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    box_set: BoxSetRead
    box_volumes: List[ItemRead]       # individual volumes in the box
    volume_count: int
    already_in_library_ids: List[int] = Field(default_factory=list)  # item_ids already in library
