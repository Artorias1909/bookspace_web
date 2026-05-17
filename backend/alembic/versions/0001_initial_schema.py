"""Initial database schema.

Revision ID: 0001
Revises:
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "series",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("total_volumes", sa.Integer, nullable=True),
        sa.Column("cover_url", sa.String(1024), nullable=True),
    )
    op.create_index("ix_series_id", "series", ["id"])
    op.create_index("ix_series_name", "series", ["name"])

    op.create_table(
        "box_sets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("series_id", sa.Integer, sa.ForeignKey("series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("isbn", sa.String(32), nullable=True, unique=True),
        sa.Column("volume_from", sa.Integer, nullable=False),
        sa.Column("volume_to", sa.Integer, nullable=False),
        sa.Column("cover_url", sa.String(1024), nullable=True),
        sa.Column("publication_year", sa.Integer, nullable=True),
    )
    op.create_index("ix_box_sets_id", "box_sets", ["id"])
    op.create_index("ix_box_sets_series_id", "box_sets", ["series_id"])
    op.create_index("ix_box_sets_isbn", "box_sets", ["isbn"])

    op.create_table(
        "items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("media_type", sa.String(32), nullable=False, server_default="book"),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("authors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("publication_year", sa.Integer, nullable=True),
        sa.Column("genre", sa.String(128), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("isbn", sa.String(32), nullable=True),
        sa.Column("cover_url", sa.String(1024), nullable=True),
        sa.Column("cover_local_path", sa.String(1024), nullable=True),
        sa.Column("language", sa.String(64), nullable=True),
        sa.Column("series_id", sa.Integer, sa.ForeignKey("series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("volume_number", sa.String(64), nullable=True),
        sa.Column("volume_title", sa.String(256), nullable=True),
        sa.Column("box_set_id", sa.Integer, sa.ForeignKey("box_sets.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_items_id", "items", ["id"])
    op.create_index("ix_items_title", "items", ["title"])
    op.create_index("ix_items_media_type", "items", ["media_type"])
    op.create_index("ix_items_publication_year", "items", ["publication_year"])
    op.create_index("ix_items_genre", "items", ["genre"])
    op.create_index("ix_items_isbn", "items", ["isbn"])
    op.create_index("ix_items_language", "items", ["language"])
    op.create_index("ix_items_series_id", "items", ["series_id"])
    op.create_index("ix_items_volume_number", "items", ["volume_number"])
    op.create_index("ix_items_box_set_id", "items", ["box_set_id"])
    op.create_index("ix_items_title_isbn", "items", ["title", "isbn"])

    op.create_table(
        "manga_volumes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_title", sa.String(512), nullable=True),
        sa.Column("romanized_title", sa.String(512), nullable=True),
        sa.Column("demographic", sa.String(32), nullable=True),
        sa.Column("reading_direction", sa.String(4), nullable=False, server_default="rtl"),
        sa.Column("dnb_id", sa.String(64), nullable=True),
        sa.Column("animexx_id", sa.String(64), nullable=True),
        sa.UniqueConstraint("item_id", name="uq_manga_volumes_item_id"),
    )
    op.create_index("ix_manga_volumes_id", "manga_volumes", ["id"])
    op.create_index("ix_manga_volumes_item_id", "manga_volumes", ["item_id"])
    op.create_index("ix_manga_volumes_demographic", "manga_volumes", ["demographic"])
    op.create_index("ix_manga_volumes_dnb_id", "manga_volumes", ["dnb_id"])

    op.create_table(
        "chapter_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("manga_volume_id", sa.Integer, sa.ForeignKey("manga_volumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("chapter_number", sa.String(16), nullable=True),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("start_page", sa.Integer, nullable=True),
        sa.Column("end_page", sa.Integer, nullable=True),
    )
    op.create_index("ix_chapter_entries_id", "chapter_entries", ["id"])
    op.create_index("ix_chapter_entries_volume_order", "chapter_entries", ["manga_volume_id", "order_index"])

    op.create_table(
        "user_item_data",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="unread"),
        sa.Column("current_page", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "item_id", name="uq_user_item_data_user_item"),
    )
    op.create_index("ix_user_item_data_id", "user_item_data", ["id"])
    op.create_index("ix_user_item_data_user_id", "user_item_data", ["user_id"])
    op.create_index("ix_user_item_data_item_id", "user_item_data", ["item_id"])
    op.create_index("ix_user_item_data_status", "user_item_data", ["status"])


def downgrade() -> None:
    op.drop_table("user_item_data")
    op.drop_table("chapter_entries")
    op.drop_table("manga_volumes")
    op.drop_table("items")
    op.drop_table("box_sets")
    op.drop_table("series")
    op.drop_table("users")
