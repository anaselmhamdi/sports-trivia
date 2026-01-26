# Sports Trivia 1v1

A 1v1 multiplayer game where two players each submit a club/franchise name (soccer or NBA), then race to name a player who played for both clubs. First correct answer wins.

## Features

- **Real-time 1v1 gameplay** - WebSocket-based for low latency
- **Multiple sports** - Soccer and NBA supported
- **Speed-based scoring** - Faster correct answers earn more points
- **Club validation** - Real-time validation with autocomplete and fuzzy matching
- **Smart aliases** - "PSG", "LAL", "Barça" all work via league-scoped aliases
- **"Stadium Pulse" UI** - Dark theme with urgency animations as timer runs down

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Flutter 3.10+ (for frontend)

### Install Everything

```bash
make all
```

### Run the Game

```bash
make run-all
# Starts backend (port 8000) + frontend (Chrome)
```

Or in separate terminals:
```bash
make run            # Terminal 1 - Backend
make frontend-web   # Terminal 2 - Frontend
```

## Make Commands

### Backend (Python/FastAPI)

| Command | Description |
|---------|-------------|
| `make install` | Install production dependencies |
| `make dev` | Install dev dependencies + pre-commit hooks |
| `make run` | Run development server (JSON data) |
| `make run-db` | Run development server (database) |
| `make seed-db` | Seed/reset the database |
| `make lint` | Run ruff linter |
| `make format` | Format code with ruff |
| `make test` | Run pytest |
| `make test-cov` | Run tests with coverage report |
| `make clean` | Clean Python build artifacts |

### Frontend (Flutter)

| Command | Description |
|---------|-------------|
| `make frontend-install` | Install Flutter dependencies |
| `make frontend-web` | Run in Chrome |
| `make frontend-run` | Run on auto-detected device |
| `make frontend-build` | Build web release |
| `make frontend-analyze` | Analyze code for issues |
| `make frontend-test` | Run Flutter tests |
| `make frontend-clean` | Clean Flutter build artifacts |

### Combined

| Command | Description |
|---------|-------------|
| `make all` | Install both backend and frontend deps |
| `make run-all` | Run backend + frontend together |
| `make clean-all` | Clean all build artifacts |

## Project Structure

```
sports-trivia/
├── backend/
│   ├── src/sports_trivia/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Environment config
│   │   ├── models/           # Pydantic data models
│   │   ├── services/         # Business logic
│   │   ├── websocket/        # WebSocket handlers
│   │   ├── db/               # SQLAlchemy models & repository
│   │   └── data/             # JSON files & SQLite database
│   ├── scripts/              # Data seeding scripts
│   └── tests/                # pytest test suite
├── frontend/
│   └── lib/
│       ├── main.dart         # App entry + routing
│       ├── theme/            # Colors, typography, theme
│       ├── models/           # Player, GameState, Room
│       ├── services/         # WebSocket service
│       ├── providers/        # Riverpod state management
│       ├── screens/          # Home, Lobby, Game, Result
│       └── widgets/          # Timer, inputs, animations
└── docs/
    ├── api.md                # WebSocket API reference
    └── visual-identity.md    # Design system documentation
```

## How to Play

1. **Create a room** - Choose your sport (NBA or Soccer) and create a room
2. **Share the code** - Give the 4-character room code to your opponent
3. **Submit clubs** - Each player submits a club/team name
4. **Race to answer** - Guess a player who played for BOTH clubs
5. **Score points** - First correct answer wins (faster = more points)
6. **Play again** - Start a new round or exit

## Design System

The frontend uses the **"Stadium Pulse"** design direction - modern sports broadcast meets luxury editorial. Key features:

- **Timer Urgency**: Colors shift cyan → orange → red as time runs out
- **Glow Effects**: Neon-style highlights on active elements
- **Animations**: Pulse, shake, confetti celebrations
- **Typography**: Bebas Neue (headlines), DM Sans (body), Oswald (numbers)

See [docs/visual-identity.md](docs/visual-identity.md) for the complete design system.

## Database

The backend uses SQLite with SQLAlchemy 2.0 ORM for storing sports data (clubs, players, and their relationships).

### Setup

```bash
cd backend

# Seed the database (creates sports_trivia.db)
uv run python scripts/seed_database.py --reset

# Verify
uv run python -c "
from sports_trivia.db import get_engine
from sqlalchemy import text
with get_engine().connect() as conn:
    print('Clubs:', conn.execute(text('SELECT COUNT(*) FROM clubs')).scalar())
    print('Players:', conn.execute(text('SELECT COUNT(*) FROM players')).scalar())
"
```

### Data Source Configuration

The backend supports two data sources, configured via the `DATA_SOURCE` environment variable:

| Value | Description |
|-------|-------------|
| `json` (default) | Load data from JSON files (legacy) |
| `db` | Use SQLite database (recommended) |

```bash
# Use database backend
export DATA_SOURCE=db
make run
```

### Seed Script Options

```bash
uv run python scripts/seed_database.py [OPTIONS]

Options:
  --nba       Seed NBA data only
  --soccer    Seed soccer data only
  --reset     Drop and recreate all tables
  -v          Verbose SQL logging
```

### Refreshing Player Data

When player data needs updating (new transfers, schema changes):

**Development:**
```bash
cd backend

# 1. Re-run transform scripts to update JSON files
uv run python scripts/transform_soccer_data.py --with-logos  # Soccer
uv run python scripts/scrape_nba_data.py                     # NBA

# 2. Drop and recreate database
rm -f data/sports_trivia.db
uv run python scripts/seed_database.py --reset
```

**Production (Fly.io):**
```bash
cd backend

# 1. Update JSON files locally (same transform scripts as above)
uv run python scripts/transform_soccer_data.py --with-logos
uv run python scripts/scrape_nba_data.py

# 2. Commit updated JSON files
git add data/*.json
git commit -m "Update player data"

# 3. Deploy (seeds automatically)
fly deploy
```

**Data Pipeline:**
```
Transfermarkt CSVs ──→ transform_soccer_data.py ──→ soccer_players.json ──┐
                                                                          ├──→ seed_database.py ──→ sports_trivia.db
NBA API ─────────────→ scrape_nba_data.py ────────→ nba_players.json ─────┘
```

### Schema

```
leagues (id, name, slug)
    └── clubs (id, league_id, key, full_name, nickname, abbreviation, alternate_names, logo, badge, ...)
            ├── club_players (club_id, player_id)  ──→  players (id, name, name_normalized)
            └── club_aliases (id, club_id, league_id, alias, alias_normalized)
```

### Club Aliases

Aliases enable flexible club lookups (e.g., "PSG" → "Paris SG", "LAL" → "Los Angeles Lakers"). Aliases are **league-scoped** so "Spurs" can map to both San Antonio Spurs (NBA) and Tottenham Hotspur (Soccer).

Sources:
- **Soccer**: `strTeamShort` and `strTeamAlternate` from TheSportsDB
- **NBA**: `abbreviation` and `nickname` from nba_api

## Development

### Running Locally with Database

**Using Make (recommended):**
```bash
make install      # Install dependencies
make seed-db      # Seed the database
make run-db       # Run with database backend
```

**Manual:**
```bash
cd backend
uv sync
uv run python scripts/seed_database.py --reset
DATA_SOURCE=db uv run uvicorn sports_trivia.main:app --reload --port 8000
```

Server runs at http://localhost:8000. Test with `test-client.html` or the Flutter frontend.

### Running Tests

```bash
cd backend

# Fast tests (no coverage)
PYTHONPATH=src uv run pytest tests/ --no-cov

# With coverage
PYTHONPATH=src uv run pytest tests/

# Specific test file
PYTHONPATH=src uv run pytest tests/test_game_manager.py --no-cov -v
```

### Code Quality

```bash
# Lint
uv run ruff check src/

# Format
uv run ruff format src/

# Type check (if mypy installed)
uv run mypy src/
```

## Deployment

### Deploy to Fly.io

```bash
cd backend

# First time setup
fly launch --no-deploy

# Deploy
fly deploy

# View logs
fly logs

# Open in browser
fly open
```

The backend will be available at `https://sports-trivia-api.fly.dev`.

### Docker (Local)

```bash
cd backend

# Build
docker build -t sports-trivia-api .

# Run
docker run -p 8000:8000 sports-trivia-api
```

## Tech Stack

- **Backend**: Python + FastAPI + WebSockets + SQLAlchemy
- **Database**: SQLite (with SQLAlchemy 2.0 ORM)
- **Data Sources**: nba_api (NBA), Transfermarkt CSVs (Soccer)
- **Frontend**: Flutter + Riverpod + go_router
- **Tooling**: uv, ruff, pytest, pre-commit

## License

MIT
