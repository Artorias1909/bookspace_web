"""SQLAlchemy ORM models mapping to the PostgreSQL schema.

Relationship graph:
    User ──< UserItemData >── Item ──< MangaVolume ──< ChapterEntry
    Series ──< Item
    BoxSet ──< Item
    Series ──< BoxSet
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Float, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    """Registered user account. The password is never stored in plaintext."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("UserItemData", back_populates="user", cascade="all, delete-orphan")


class Series(Base):
    """Shared series record grouping related volumes (e.g., a manga run or book trilogy)."""
    __tablename__ = "series"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False, index=True)
    type = Column(String(32), nullable=False)
    total_volumes = Column(Integer, nullable=True)
    cover_url = Column(String(1024), nullable=True)

    items = relationship("Item", back_populates="series")
    box_sets = relationship("BoxSet", back_populates="series")


class BoxSet(Base):
    """A collector box / Sammelschuber containing a range of volumes from a series."""
    __tablename__ = "box_sets"

    id = Column(Integer, primary_key=True, index=True)
    series_id = Column(Integer, ForeignKey("series.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(256), nullable=True)          # arc name, e.g. "East Blue"
    isbn = Column(String(32), nullable=True, unique=True, index=True)
    volume_from = Column(Integer, nullable=False)
    volume_to = Column(Integer, nullable=False)
    cover_url = Column(String(1024), nullable=True)
    publication_year = Column(Integer, nullable=True)

    series = relationship("Series", back_populates="box_sets")
    items = relationship("Item", back_populates="box_set")


class Item(Base):
    """A single book, manga, or comic volume. media_type discriminates the subtype.

    When media_type == "manga", a corresponding MangaVolume row holds additional metadata.
    Items may belong to a Series and/or a BoxSet; both FK columns allow NULL.
    """
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    # Discriminator — "book", "manga", "comic"
    media_type = Column(String(32), nullable=False, default="book", index=True)
    title = Column(String(512), nullable=False, index=True)
    authors = Column(JSONB, nullable=False, server_default="[]")
    publication_year = Column(Integer, nullable=True, index=True)
    genre = Column(String(128), nullable=True, index=True)
    page_count = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    isbn = Column(String(32), nullable=True, index=True)
    cover_url = Column(String(1024), nullable=True)
    cover_local_path = Column(String(1024), nullable=True)
    language = Column(String(64), nullable=True, index=True)
    series_id = Column(Integer, ForeignKey("series.id", ondelete="SET NULL"), nullable=True, index=True)
    volume_number = Column(String(64), nullable=True, index=True)
    volume_title = Column(String(256), nullable=True)
    box_set_id = Column(Integer, ForeignKey("box_sets.id", ondelete="SET NULL"), nullable=True, index=True)

    series = relationship("Series", back_populates="items")
    box_set = relationship("BoxSet", back_populates="items")
    library_entries = relationship("UserItemData", back_populates="item", cascade="all, delete-orphan")
    # One-to-one extension: only present when media_type == "manga"
    manga_meta = relationship("MangaVolume", back_populates="item", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_items_title_isbn", "title", "isbn"),
    )


class MangaVolume(Base):
    """Manga-specific metadata extending Item (1:1 relationship)."""
    __tablename__ = "manga_volumes"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(
        Integer,
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Titles
    original_title = Column(String(512), nullable=True)   # Japanese title (kanji/kana)
    romanized_title = Column(String(512), nullable=True)  # Romaji

    # Classification
    # shounen | shoujo | seinen | josei | kodomomuke
    demographic = Column(String(32), nullable=True, index=True)
    reading_direction = Column(String(4), nullable=False, default="rtl")  # rtl = standard manga

    # External IDs for cross-referencing
    dnb_id = Column(String(64), nullable=True, index=True)    # DNB catalog record ID
    animexx_id = Column(String(64), nullable=True)             # Animexx entry ID (future)

    item = relationship("Item", back_populates="manga_meta")
    chapters = relationship(
        "ChapterEntry",
        back_populates="manga_volume",
        cascade="all, delete-orphan",
        order_by="ChapterEntry.order_index",
    )

    __table_args__ = (
        UniqueConstraint("item_id", name="uq_manga_volumes_item_id"),
    )


class ChapterEntry(Base):
    """Individual chapter record within a manga volume."""
    __tablename__ = "chapter_entries"

    id = Column(Integer, primary_key=True, index=True)
    manga_volume_id = Column(
        Integer,
        ForeignKey("manga_volumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order_index = Column(Integer, nullable=False)         # display/sort order
    chapter_number = Column(String(16), nullable=True)    # "1", "1.5", "Bonus", None for extras
    title = Column(String(256), nullable=True)
    start_page = Column(Integer, nullable=True)
    end_page = Column(Integer, nullable=True)

    manga_volume = relationship("MangaVolume", back_populates="chapters")

    __table_args__ = (
        Index("ix_chapter_entries_volume_order", "manga_volume_id", "order_index"),
    )


class UserItemData(Base):
    """Per-user reading state for a single Item (status, current page, calculated progress).

    The (user_id, item_id) pair is unique — a user can add each item only once.
    """
    __tablename__ = "user_item_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="unread", index=True)
    current_page = Column(Integer, nullable=False, default=0)
    progress_percent = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="items")
    item = relationship("Item", back_populates="library_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_user_item_data_user_item"),
    )
