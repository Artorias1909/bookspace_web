.PHONY: test build up down logs clean shell-backend shell-db

# ── Tests ────────────────────────────────────────────────────────────────────

test:
	cd backend && python -m pytest --tb=short -q

test-verbose:
	cd backend && python -m pytest --tb=long -v

test-coverage:
	cd backend && python -m pytest --cov=app --cov-report=term-missing -q

# ── Docker ───────────────────────────────────────────────────────────────────

build: test
	docker-compose build

up: build
	docker-compose up -d
	@echo "Bookspace läuft unter https://localhost"

down:
	docker-compose down

restart: down up

# ── Logs & Debugging ─────────────────────────────────────────────────────────

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-db:
	docker-compose logs -f db

shell-backend:
	docker-compose exec backend bash

shell-db:
	docker-compose exec db psql -U bookspace_user -d bookspace

# ── Aufräumen ────────────────────────────────────────────────────────────────

clean:
	docker-compose down -v --remove-orphans
	@echo "Container und Volumes entfernt."
