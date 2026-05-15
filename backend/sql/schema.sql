-- PostgreSQL schema for Bookspace

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(128) NOT NULL UNIQUE,
    hashed_password VARCHAR(256) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE series (
    id SERIAL PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    type VARCHAR(32) NOT NULL,
    total_volumes INTEGER NULL
);

CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    media_type VARCHAR(32) NOT NULL DEFAULT 'book',
    title VARCHAR(512) NOT NULL,
    authors JSONB NOT NULL DEFAULT '[]',
    publication_year INTEGER,
    genre VARCHAR(128),
    page_count INTEGER,
    description TEXT,
    isbn VARCHAR(32),
    cover_url VARCHAR(1024),
    cover_local_path VARCHAR(1024),
    language VARCHAR(64),
    series_id INTEGER REFERENCES series(id) ON DELETE SET NULL,
    volume_number VARCHAR(64),
    volume_title VARCHAR(256)
);

CREATE INDEX ix_items_id ON items(id);
CREATE INDEX ix_items_media_type ON items(media_type);
CREATE INDEX ix_items_title ON items(title);
CREATE INDEX ix_items_genre ON items(genre);
CREATE INDEX ix_items_isbn ON items(isbn);
CREATE INDEX ix_items_language ON items(language);
CREATE INDEX ix_items_publication_year ON items(publication_year);
CREATE INDEX ix_items_series_id ON items(series_id);
CREATE INDEX ix_items_volume_number ON items(volume_number);
CREATE UNIQUE INDEX ix_items_title_authors ON items(title, isbn);

CREATE TABLE manga_volumes (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    original_title VARCHAR(512),
    romanized_title VARCHAR(512),
    demographic VARCHAR(32),
    reading_direction VARCHAR(4) NOT NULL DEFAULT 'ltr',
    dnb_id VARCHAR(64),
    animexx_id VARCHAR(64),
    CONSTRAINT uq_manga_volumes_item_id UNIQUE (item_id)
);

CREATE INDEX ix_manga_volumes_id ON manga_volumes(id);
CREATE INDEX ix_manga_volumes_item_id ON manga_volumes(item_id);
CREATE INDEX ix_manga_volumes_demographic ON manga_volumes(demographic);
CREATE INDEX ix_manga_volumes_dnb_id ON manga_volumes(dnb_id);

CREATE TABLE chapter_entries (
    id SERIAL PRIMARY KEY,
    manga_volume_id INTEGER NOT NULL REFERENCES manga_volumes(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    chapter_number VARCHAR(16),
    title VARCHAR(256),
    start_page INTEGER,
    end_page INTEGER
);

CREATE INDEX ix_chapter_entries_id ON chapter_entries(id);
CREATE INDEX ix_chapter_entries_manga_volume_id ON chapter_entries(manga_volume_id);
CREATE INDEX ix_chapter_entries_volume_order ON chapter_entries(manga_volume_id, order_index);

CREATE TABLE user_item_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'unread',
    current_page INTEGER NOT NULL DEFAULT 0,
    progress_percent DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_user_item_data_user_id ON user_item_data(user_id);
CREATE INDEX ix_user_item_data_item_id ON user_item_data(item_id);
CREATE INDEX ix_user_item_data_status ON user_item_data(status);
