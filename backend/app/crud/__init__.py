"""CRUD layer — public re-exports from domain submodules.

Import patterns used throughout the codebase:
    from .. import crud
    crud.get_user_by_username(db, ...)
"""
from .users import get_user_by_username, create_user, authenticate_user
from .series import create_series, get_series, list_series, find_or_create_series, bulk_update_series_status, find_series_by_name, delete_user_series_entries
from .box_sets import create_box_set, get_box_set_by_isbn, find_or_create_volume_item
from .items import (
    create_item,
    get_item,
    get_item_by_isbn,
    search_items,
    update_item,
    assign_item_to_series,
    list_series_items,
)
from .user_items import (
    create_user_item_data,
    get_user_item,
    get_user_item_by_item_id,
    count_user_items,
    list_user_items,
    update_user_item_data,
    delete_user_item,
    calculate_progress,
)
from .isbn import (
    parse_isbn_metadata,
    parse_google_book,
    parse_open_library_api,
    parse_open_library,
    get_isbn_from_info,
    extract_series_fields,
)
from .manga import get_manga_volume, upsert_manga_volume

__all__ = [
    # users
    "get_user_by_username",
    "create_user",
    "authenticate_user",
    # series
    "create_series",
    "get_series",
    "list_series",
    "find_or_create_series",
    "bulk_update_series_status",
    "find_series_by_name",
    "delete_user_series_entries",
    # box sets
    "create_box_set",
    "get_box_set_by_isbn",
    "find_or_create_volume_item",
    # items
    "create_item",
    "get_item",
    "get_item_by_isbn",
    "search_items",
    "update_item",
    "assign_item_to_series",
    "list_series_items",
    # user items
    "create_user_item_data",
    "get_user_item",
    "get_user_item_by_item_id",
    "count_user_items",
    "list_user_items",
    "update_user_item_data",
    "delete_user_item",
    "calculate_progress",
    # isbn
    "parse_isbn_metadata",
    "parse_google_book",
    "parse_open_library_api",
    "parse_open_library",
    "get_isbn_from_info",
    "extract_series_fields",
    # manga
    "get_manga_volume",
    "upsert_manga_volume",
]
