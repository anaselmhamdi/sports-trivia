# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sports Trivia 1v1 is a real-time multiplayer game where two players submit sports clubs (NBA or Soccer), then race to name a player who played for both. Built with FastAPI (WebSockets) + Flutter (Riverpod).

## Commands

### Backend (Python with uv)

```bash
make dev                  # Install with dev deps + pre-commit hooks
make run                  # Run server with JSON data (port 8000)
make run-db               # Run server with SQLite database
make seed-db              # Create/reset database from JSON data
make test                 # Run pytest
make lint                 # ruff check
make format               # ruff format
```

Single test file: `cd backend && PYTHONPATH=src pytest tests/test_game_manager.py -v`

### Frontend (Flutter)

```bash
make frontend-install     # Install Flutter deps
make frontend-web         # Run in Chrome
make frontend-test        # Run Flutter tests
```

### Docker

```bash
make docker-build         # Build multi-stage image
make docker-run           # Run locally (port 8000)
```

## Architecture

### Backend Structure (`backend/src/sports_trivia/`)

- **`main.py`** - FastAPI app, WebSocket endpoint `/ws`, HTTP endpoints for validation
- **`services/game_manager.py`** - Game state machine with phases: `WAITING_FOR_PLAYERS` → `WAITING_FOR_CLUBS` → `GUESSING` → `ROUND_END`
- **`services/room_manager.py`** - Room lifecycle, 30-min TTL cleanup
- **`websocket/handlers.py`** - Connection management, message dispatch
- **`websocket/events.py`** - `ClientEvent` and `ServerEvent` enums
- **`db/models.py`** - SQLAlchemy ORM (League, Club, ClubAlias, Player)
- **`db/repository.py`** - Database queries with fuzzy matching

### Frontend Structure (`frontend/lib/`)

- **`providers/game_orchestrator.dart`** - Pure state transition functions (no side effects)
- **`providers/game_provider.dart`** - Riverpod StateNotifier subscribing to WebSocket events
- **`services/websocket_service.dart`** - WebSocket client with typed event streams
- **`theme/app_colors.dart`** - "Stadium Pulse" color palette with timer urgency gradients

### Key Patterns

**Per-room locking** - All room state mutations wrapped in `async with room.get_lock()`

**State versioning** - `GameState.version` increments on mutations; clients detect stale state

**Fuzzy matching** - Uses `rapidfuzz` (85% threshold) for player name matching

**Immutable frontend state** - All GameState updates via `copyWith()`, orchestrator methods are pure functions

### WebSocket Protocol

Client sends: `create_room`, `join_room`, `submit_club`, `submit_guess`, `sync_state`, `play_again`

Server broadcasts: `room_created`, `room_joined`, `club_submitted`, `guessing_started`, `guess_result`, `round_ended`, `state_sync`

Message format: `{"event": "event_name", "data": {...}}`

### Data Sources

**JSON mode** (default): Reads from `data/nba_players.json`, `data/soccer_players.json`

**Database mode** (`DATA_SOURCE=db`): SQLite at `data/sports_trivia.db` with League→Club→Player schema. ClubAlias table enables fuzzy lookups.

## Refreshing Player Data

When player data needs to be updated (new transfers, schema changes, etc.), follow this flow:

### Development (Local)

```bash
cd backend

# 1. Re-run transform scripts to update JSON files
uv run python scripts/transform_soccer_data.py --with-logos  # Soccer data from CSVs
uv run python scripts/scrape_nba_data.py                     # NBA data from nba_api

# 2. Drop and recreate database with new schema/data
rm -f data/sports_trivia.db
uv run python scripts/seed_database.py --reset

# 3. Verify
uv run python -c "
from sports_trivia.db import get_engine
from sqlalchemy import text
with get_engine().connect() as conn:
    print('Clubs:', conn.execute(text('SELECT COUNT(*) FROM clubs')).scalar())
    print('Players:', conn.execute(text('SELECT COUNT(*) FROM players')).scalar())
"
```

### Production (Fly.io)

```bash
cd backend

# 1. Update JSON files locally (same as dev steps 1)
uv run python scripts/transform_soccer_data.py --with-logos
uv run python scripts/scrape_nba_data.py

# 2. Commit the updated JSON files
git add data/*.json
git commit -m "Update player data"

# 3. Deploy (Dockerfile runs seed_database.py on build)
fly deploy

# 4. Verify via SSH if needed
fly ssh console
python scripts/seed_database.py --reset
```

### Data Pipeline Overview

```
Transfermarkt CSVs ──→ transform_soccer_data.py ──→ soccer_players.json ──┐
                                                                          ├──→ seed_database.py ──→ sports_trivia.db
NBA API ─────────────→ scrape_nba_data.py ────────→ nba_players.json ─────┘
```

**Key files:**
- `backend/scripts/transform_soccer_data.py` - Transforms Transfermarkt CSVs, fetches logos from TheSportsDB
- `backend/scripts/scrape_nba_data.py` - Scrapes NBA franchise player history
- `backend/scripts/seed_database.py` - Seeds SQLite from JSON files
- `backend/data/*.json` - Intermediate JSON files (committed to repo)
- `backend/data/sports_trivia.db` - SQLite database (not committed, generated on deploy)

## Environment Variables

```env
DATA_SOURCE=json          # or "db" for SQLite
PORT=8000
DEFAULT_TIMER_SECONDS=60
```

## Testing

Tests in `backend/tests/` cover:
- `test_game_manager.py` - State transitions, fuzzy matching
- `test_concurrency.py` - Race conditions, per-room locking
- `test_state_sync.py` - Reconnection scenarios
- `test_websocket.py` - Full game flow integration
