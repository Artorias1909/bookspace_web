# Bookspace

Bookspace is a full-stack library management system for books, manga, and comics.

## Architecture

- Backend: Python + FastAPI
- Frontend: React
- Database: PostgreSQL
- API: REST

## Features

- User registration and login with hashed passwords
- Item metadata import via ISBN with Google Books and Open Library fallback
- Series support with manual assignment and automatic volume parsing
- Responsive cover grid and sortable list view
- User-specific library entries and progress tracking
- Global search across title, authors, genre, and series metadata

## Local Setup

1. Copy environment template:

```bash
cp .env.example .env
```

2. Start PostgreSQL and backend/frontend with Docker Compose:

```bash
docker-compose up --build
```

3. Access:

- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Frontend app: `http://localhost:3000`

## Backend Commands

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Frontend Commands

```bash
cd frontend
npm install
npm start
```

## Future Improvements

- Add pagination metadata and total counts to API responses
- Add unit/integration tests for both backend and frontend
- Add user-specific bookshelf categories and tags
- Add copy management and ISBN history deduplication
- Add deployment support for Kubernetes and managed Postgres
