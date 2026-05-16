# Bookspace

Personal library management for books, manga, and comics. Track your reading progress, import titles by ISBN barcode scan, and organise your collection by series.

## Features

- **ISBN import** — scan or type any ISBN-10/13 to automatically pull metadata from Deutsche Nationalbibliothek, Google Books, and Open Library
- **Manga enrichment** — manga titles are additionally enriched with AniList (high-res cover art, Japanese title) and Manga-Passion (official German publisher data, canonical series name, German volume subtitle)
- **Sammelbox detection** — collector box ISBNs (Sammelschuber) are automatically expanded into their individual volumes, each fully enriched in parallel
- **Series management** — volumes are auto-linked to their series; bulk status updates and series-wide deletion supported
- **Progress tracking** — per-volume status (unread / reading / completed / owned / wishlist) and page-level progress with percentage
- **Cover grid & sortable list** — two views with search, status filter, and sort by title, author, year, or status
- **Duplicate prevention** — re-scanning an already-owned ISBN is detected and flagged without creating duplicates
- **User accounts** — isolated libraries per user with JWT authentication and password strength validation

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg |
| Database | PostgreSQL |
| Frontend | React 18 |
| Proxy | nginx |
| Container | Docker Compose |

## Quick start

```bash
cp .env.example .env          # set SECRET_KEY, optionally GOOGLE_BOOKS_API_KEY
docker compose up --build
```

| Service | URL |
|---|---|
| App | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://user:pass@host/db` |
| `SECRET_KEY` | yes | Random string ≥ 32 chars for JWT signing |
| `GOOGLE_BOOKS_API_KEY` | no | Dedicated quota; falls back to anonymous shared limit |
| `FRONTEND_URL` | no | CORS allowed origin (default: `http://localhost:3000`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | JWT lifetime in minutes (default: `60`) |

## Local development without Docker

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm start
```

## Tests

```bash
cd backend
pip install pytest pytest-asyncio pytest-cov respx aiosqlite
pytest
```

The suite runs against an in-memory SQLite database — no Postgres instance required. Coverage is enforced at 100%.

## API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/token` | Login (OAuth2 password grant) |
| `POST` | `/import/isbn` | Import item or Sammelbox by ISBN |
| `GET` | `/user-items/` | List library (paginated, filterable, sortable) |
| `POST` | `/user-items/` | Add item to library |
| `PUT` | `/user-items/{id}` | Update status or reading progress |
| `DELETE` | `/user-items/{id}` | Remove entry from library |
| `GET` | `/series/` | List all series |
| `PUT` | `/series/{id}/status` | Bulk-set status for all volumes in a series |
| `DELETE` | `/series/{id}/library` | Remove entire series from library |
| `GET` | `/items/` | Global item search |

## ISBN import pipeline

```
1.  Strip invisible Unicode formatting characters from input
2a. Cache check — return existing item with ownership flag (no duplicate import)
2b. Cache check — return existing Sammelbox with per-volume ownership list
3.  Fetch DNB (MARC21 via SRU) and Google Books / Open Library in parallel
4.  Merge: DNB wins for structured fields; Google/OL fills cover and gaps
5.  Detect Sammelbox keyword → expand to individual volumes (one per band)
6.  Manga: enrich with AniList — series cover, Japanese original title
7.  Manga: enrich with Manga-Passion — publisher cover, canonical series name, German subtitle
8.  Persist Item + MangaVolume metadata + Series link
```

## Database schema (key tables)

```
users           id · username · hashed_password
series          id · name · type (book|manga|comic) · total_volumes
box_sets        id · series_id · name · isbn · volume_from · volume_to
items           id · title · media_type · isbn · series_id · volume_number · box_set_id · …
manga_volumes   id · item_id · original_title · demographic · reading_direction · dnb_id
chapter_entries id · manga_volume_id · order_index · chapter_number · title
user_item_data  id · user_id · item_id · status · current_page · progress_percent
```
