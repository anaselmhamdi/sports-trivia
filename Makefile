.PHONY: install dev lint format test test-cov run run-db seed-db clean
.PHONY: frontend-install frontend-run frontend-web frontend-build frontend-analyze frontend-test frontend-clean
.PHONY: all run-all clean-all
.PHONY: docker-build docker-build-fast docker-run

# =============================================================================
# BACKEND (Python/FastAPI)
# =============================================================================

# Install production dependencies
install:
	cd backend && uv sync

# Install with dev dependencies
dev:
	cd backend && uv sync --all-extras
	pre-commit install

# Run linter
lint:
	cd backend && uv run ruff check src tests

# Format code
format:
	cd backend && uv run ruff format src tests
	cd backend && uv run ruff check --fix src tests

# Run tests
test:
	cd backend && uv run pytest

# Run tests with coverage report
test-cov:
	cd backend && uv run pytest --cov-report=html

# Run development server (uses JSON data by default)
run:
	cd backend && uv run uvicorn sports_trivia.main:app --reload --host 0.0.0.0 --port 8000

# Run with database backend
run-db:
	cd backend && DATA_SOURCE=db uv run uvicorn sports_trivia.main:app --reload --host 0.0.0.0 --port 8000

# Seed the database (creates/resets sports_trivia.db)
seed-db:
	cd backend && uv run python scripts/seed_database.py --reset

# Scrape NBA player data (run periodically to update local cache)
scrape-nba:
	cd backend && uv run python scripts/scrape_nba_data.py

# =============================================================================
# FRONTEND (Flutter)
# =============================================================================

# Install Flutter dependencies
frontend-install:
	cd frontend && flutter pub get

# Run Flutter app (auto-detects device)
frontend-run:
	cd frontend && flutter run

# Run Flutter app in Chrome
frontend-web:
	cd frontend && flutter run -d chrome

# Build Flutter web release
frontend-build:
	cd frontend && flutter build web --release

# Analyze Flutter code
frontend-analyze:
	cd frontend && flutter analyze

# Run Flutter tests
frontend-test:
	cd frontend && flutter test

# =============================================================================
# COMBINED
# =============================================================================

# Install all dependencies (backend + frontend)
all: install frontend-install

# Run both backend and frontend together
run-all:
	@echo "Starting backend (port 8000) and frontend..."
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn sports_trivia.main:app --reload --host 0.0.0.0 --port 8000) & \
	sleep 2 && (cd frontend && flutter run -d chrome) & \
	wait

# =============================================================================
# DOCKER
# =============================================================================

# Build Docker image (uses pre-generated soccer data with logos)
docker-build:
	docker build -t clutch .

# Run Docker container locally
docker-run:
	docker run -p 8000:8000 clutch

# =============================================================================
# CLEANUP
# =============================================================================

# Clean backend build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# Clean Flutter build artifacts
frontend-clean:
	cd frontend && flutter clean
	rm -rf frontend/build

# Clean everything
clean-all: clean frontend-clean
