# Architecture Overview

## System Components

```
┌─────────────────┐         WebSocket          ┌─────────────────┐
│  Flutter Client │◄─────────────────────────►│  FastAPI Server │
│    (Web/Mobile) │                            │                 │
└─────────────────┘                            │  ┌───────────┐  │
                                               │  │   Room    │  │
┌─────────────────┐         WebSocket          │  │  Manager  │  │
│  Flutter Client │◄─────────────────────────►│  └───────────┘  │
│   (Opponent)    │                            │        │        │
└─────────────────┘                            │  ┌───────────┐  │
                                               │  │   Game    │  │
                                               │  │  Manager  │  │
                                               │  └───────────┘  │
                                               │        │        │
                                               │  ┌───────────┐  │
                                               │  │   Data    │  │
                                               │  │ Services  │  │
                                               │  └───────────┘  │
                                               └─────────────────┘
                                                       │
                                               ┌───────┴───────┐
                                               │               │
                                          ┌────────┐    ┌────────────┐
                                          │nba_api │    │API-Football│
                                          └────────┘    └────────────┘
```

## Component Responsibilities

### ConnectionManager
- Manages WebSocket connections
- Maps players to rooms
- Handles message routing and broadcasting

### RoomManager
- Creates and destroys rooms
- Manages player join/leave
- Generates unique room codes

### GameManager
- Implements game state machine
- Validates clubs and guesses
- Calculates scores
- Manages round lifecycle

### Data Services
- **NBADataService**: Player/team lookups using nba_api
- **SoccerDataService**: Player/club lookups using API-Football
- Both support mock data for testing

## Game State Machine

```
WAITING_FOR_PLAYERS (1 player in room)
       │
       ▼ (2nd player joins)
WAITING_FOR_CLUBS (both players submit a club)
       │
       ▼ (both clubs submitted)
VALIDATING_CLUBS (verify clubs exist, find common players)
       │
       ├── (no common players) → Error, re-pick clubs
       │
       ▼ (valid - common players exist)
GUESSING_PHASE (60s timer, race to answer)
       │
       ├── (correct guess) → ROUND_END (winner declared)
       ├── (timeout) → ROUND_END (no winner, show valid answers)
       │
       ▼
ROUND_END
       │
       ├── (play again) → WAITING_FOR_CLUBS
       └── (exit) → GAME_OVER
```

## Data Flow

### Room Creation
1. Client sends `create_room` with player name and sport
2. RoomManager generates room code and creates Room
3. Player added to room (phase: WAITING_FOR_PLAYERS)
4. Server responds with `room_created`

### Club Submission
1. Client sends `submit_club` with club name
2. GameManager validates club exists
3. If valid, stores submission and broadcasts `club_submitted`
4. When both submitted, GameManager finds common players
5. If common players exist, broadcasts `guessing_started`
6. If no common players, broadcasts `clubs_invalid`

### Guessing
1. Client sends `submit_guess` with player name
2. GameManager checks against valid answers
3. Broadcasts `guess_result` (correct or incorrect)
4. If correct, ends round and broadcasts `round_ended`
5. If timeout, also broadcasts `round_ended`

## Scoring

Points = `max_points` - `seconds_elapsed`

Example: If `max_points = 100` and answer submitted at 15 seconds:
- Points earned: 100 - 15 = 85

## Technology Choices

| Choice | Rationale |
|--------|-----------|
| FastAPI | Native WebSocket support, async, type hints |
| Pydantic | Data validation, serialization |
| nba_api | Direct Python integration for NBA data |
| WebSockets | Low latency for competitive gameplay |
| uv | Fast, reliable Python package management |
