// API types — mirrored from backend Pydantic schemas

export interface User {
  id: number;
  username: string;
}

export interface Series {
  id: number;
  name: string;
  type: string | null;
  total_volumes: number | null;
  cover_url: string | null;
}

export interface ChapterEntry {
  id: number;
  chapter_number: string;
  title: string | null;
  page_start: number | null;
  page_end: number | null;
}

export interface MangaVolume {
  id: number;
  item_id: number;
  demographic: string | null;
  original_title: string | null;
  romanized_title: string | null;
  reading_direction: string | null;
  dnb_id: string | null;
  chapters: ChapterEntry[];
}

export interface Item {
  id: number;
  isbn: string | null;
  title: string;
  authors: string[];
  media_type: string | null;
  cover_url: string | null;
  page_count: number | null;
  publication_year: number | null;
  publisher: string | null;
  language: string | null;
  genre: string | null;
  description: string | null;
  series_id: number | null;
  volume_number: string | null;
  volume_title: string | null;
  series: Series | null;
  manga_meta: MangaVolume | null;
}

export type ReadingStatus = "unread" | "reading" | "completed" | "owned" | "wishlist";

export interface UserItemData {
  id: number;
  item_id: number;
  status: ReadingStatus | null;
  current_page: number | null;
  progress_percent: number;
  item: Item;
  created_at: string;
  updated_at: string;
}

export interface PagedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
}

export interface LibraryParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  q?: string;
  status?: ReadingStatus;
}

// Display types for grouped library view
export interface SingleDisplayItem {
  type: "single";
  id: number;
  entry: UserItemData;
}

export interface SeriesDisplayGroup {
  type: "series";
  id: string;
  seriesId: number;
  seriesName: string;
  seriesCover: string | null;
  seriesData: Series | null;
  entries: UserItemData[];
}

export type DisplayItem = SingleDisplayItem | SeriesDisplayGroup;
