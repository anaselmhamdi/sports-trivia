# Development Guide

## Prerequisites

- **Python 3.11+** - Required for the backend
- **uv** - Fast Python package manager ([install](https://github.com/astral-sh/uv))
- **Flutter** - For frontend development (optional for backend-only work)
- **Git** - Version control

## Initial Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/sports-trivia.git
cd sports-trivia
```

### 2. Install backend dependencies

```bash
# Install production + dev dependencies
make dev

# This also installs pre-commit hooks
```

### 3. Verify installation

```bash
# Run linter (should pass with no errors)
make lint

# Run tests (should all pass)
make test
```

## Running Locally

### Backend Server

```bash
make run
```

This starts the FastAPI server at `http://localhost:8000` with hot reload enabled.

- **API docs**: http://localhost:8000/docs (Swagger UI)
- **WebSocket**: ws://localhost:8000/ws
- **Health check**: http://localhost:8000/health

### Frontend (Coming Soon)

```bash
cd frontend
flutter run -d chrome  # For web
flutter run            # For mobile
```

## Development Workflow

### Code Style

We use **Ruff** for linting and formatting:

```bash
# Check for issues
make lint

# Auto-fix issues and format
make format
```

Ruff configuration is in `backend/pyproject.toml`.

### Testing

```bash
# Run all tests
make test

# Run with coverage report
make test-cov
# Coverage HTML report: backend/htmlcov/index.html

# Run specific test file
cd backend && uv run pytest tests/test_room_manager.py

# Run specific test
cd backend && uv run pytest tests/test_room_manager.py::TestRoomManager::test_create_room -v
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`:

- Trailing whitespace removal
- End-of-file fixing
- YAML validation
- Ruff linting and formatting

To run manually:

```bash
pre-commit run --all-files
```

## Project Structure

```
backend/
├── src/sports_trivia/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, routes, WebSocket endpoint
│   ├── config.py         # Environment config (Pydantic Settings)
│   ├── models/
│   │   ├── game.py       # Sport, GamePhase, Player, GameState
│   │   └── room.py       # Room model
│   ├── services/
│   │   ├── room_manager.py   # Room lifecycle
│   │   ├── game_manager.py   # Game logic & state machine
│   │   ├── nba_data.py       # NBA player/team lookups
│   │   └── soccer_data.py    # Soccer player/club lookups
│   └── websocket/
│       ├── events.py         # Event type definitions
│       └── handlers.py       # WebSocket event handlers
└── tests/
    ├── conftest.py           # Shared fixtures
    ├── test_room_manager.py
    ├── test_game_manager.py
    ├── test_nba_data.py
    └── test_websocket.py     # Integration tests
```

## Environment Variables

Create a `.env` file in the project root:

```env
# API-Football (soccer data) - optional, uses mock data without
API_FOOTBALL_KEY=your_key_here

# Server config
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Game settings
DEFAULT_TIMER_SECONDS=60
MAX_POINTS_PER_ROUND=100
```

## Adding New Features

### Adding a New Sport

1. Add sport to `Sport` enum in `models/game.py`
2. Create data service in `services/` (e.g., `nfl_data.py`)
3. Update `GameManager._get_data_service()` to return new service
4. Add mock data for testing
5. Write tests

### Adding a New WebSocket Event

1. Add event to `ClientEvent` or `ServerEvent` in `websocket/events.py`
2. Add handler method in `WebSocketHandler`
3. Register handler in `_handle_message()` routing dict
4. Update API documentation
5. Write tests

## Troubleshooting

### "Module not found" errors

Make sure you're using uv to run commands:

```bash
cd backend && uv run python -c "from sports_trivia import main"
```

### Tests failing with import errors

Ensure you've installed dev dependencies:

```bash
make dev
```

### Pre-commit hooks not running

Reinstall hooks:

```bash
pre-commit install
```

## Contributing

1. Create a feature branch
2. Make changes
3. Ensure `make lint` and `make test` pass
4. Commit (pre-commit hooks will run)
5. Push and create PR
