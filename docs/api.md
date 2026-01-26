# WebSocket API Reference

## Connection

Connect to the WebSocket endpoint:

```
ws://localhost:8000/ws
```

All messages are JSON objects with `event` and `data` fields:

```json
{
  "event": "event_name",
  "data": { ... }
}
```

## Client → Server Events

### `create_room`

Create a new game room.

**Payload:**
```json
{
  "player_name": "Alice",
  "sport": "nba"  // or "soccer"
}
```

**Response:** `room_created`

---

### `join_room`

Join an existing room.

**Payload:**
```json
{
  "room_code": "ABC123",
  "player_name": "Bob"
}
```

**Response:** `room_joined` or `error`

---

### `submit_club`

Submit a club/team for the round.

**Payload:**
```json
{
  "club_name": "Los Angeles Lakers"
}
```

**Response:** `club_submitted` (broadcast), then `guessing_started` or `clubs_invalid`

---

### `submit_guess`

Guess a player who played for both clubs.

**Payload:**
```json
{
  "player_name": "LeBron James"
}
```

**Response:** `guess_result` (broadcast), then `round_ended` if correct

---

### `play_again`

Start a new round after round ends.

**Payload:** `{}`

**Response:** `new_round` (broadcast)

---

### `leave_room`

Leave the current room.

**Payload:** `{}`

**Response:** Disconnects, other player receives `player_left`

---

### `sync_state`

Request full game state (used after reconnection).

**Payload:** `{}`

**Response:** `state_sync`

---

### `ping`

Keep-alive ping.

**Payload:** `{}`

**Response:** `pong`

---

## Server → Client Events

### `room_created`

Sent when room is successfully created.

```json
{
  "event": "room_created",
  "data": {
    "room_code": "ABC123",
    "sport": "nba",
    "player": {
      "id": "uuid",
      "name": "Alice",
      "score": 0
    }
  }
}
```

---

### `room_joined`

Sent to player who joins a room.

```json
{
  "event": "room_joined",
  "data": {
    "room_code": "ABC123",
    "sport": "nba",
    "players": [
      {"id": "uuid1", "name": "Alice", "score": 0},
      {"id": "uuid2", "name": "Bob", "score": 0}
    ],
    "phase": "waiting_for_clubs"
  }
}
```

---

### `player_joined`

Broadcast when another player joins.

```json
{
  "event": "player_joined",
  "data": {
    "player": {
      "id": "uuid",
      "name": "Bob",
      "score": 0
    },
    "phase": "waiting_for_clubs"
  }
}
```

---

### `player_left`

Broadcast when a player leaves.

```json
{
  "event": "player_left",
  "data": {
    "player_id": "uuid",
    "phase": "waiting_for_players"
  }
}
```

---

### `club_submitted`

Broadcast when a player submits a club.

```json
{
  "event": "club_submitted",
  "data": {
    "player_id": "uuid"
  }
}
```

---

### `clubs_invalid`

Broadcast when submitted clubs have no common players.

```json
{
  "event": "clubs_invalid",
  "data": {
    "error": "No players found who played for both Lakers and Celtics"
  }
}
```

---

### `guessing_started`

Broadcast when guessing phase begins.

```json
{
  "event": "guessing_started",
  "data": {
    "clubs": ["Los Angeles Lakers", "Miami Heat"],
    "deadline": 1706123456.789,
    "valid_count": 3
  }
}
```

---

### `guess_result`

Broadcast after each guess attempt.

```json
{
  "event": "guess_result",
  "data": {
    "correct": false,
    "player_id": "uuid",
    "guess": "Kobe Bryant"
  }
}
```

---

### `round_ended`

Broadcast when round ends (win or timeout).

```json
{
  "event": "round_ended",
  "data": {
    "winner_id": "uuid",  // or null if timeout
    "winning_answer": "LeBron James",  // or null
    "points": 85,  // points awarded
    "valid_answers": ["LeBron James", "Shaquille O'Neal"],
    "scores": {
      "uuid1": 85,
      "uuid2": 0
    }
  }
}
```

---

### `new_round`

Broadcast when a new round starts.

```json
{
  "event": "new_round",
  "data": {
    "phase": "waiting_for_clubs"
  }
}
```

---

### `state_sync`

Full game state snapshot (sent after `sync_state` request or reconnection).

```json
{
  "event": "state_sync",
  "data": {
    "version": 42,
    "room_code": "ABCD",
    "sport": "nba",
    "phase": "guessing",
    "my_club": "Los Angeles Lakers",
    "my_club_logo": "https://...",
    "opponent_club": "Miami Heat",
    "opponent_club_logo": "https://...",
    "deadline": 1706300000.0,
    "valid_answer_count": 37,
    "self_player": {
      "id": "uuid1",
      "name": "Alice",
      "score": 100,
      "submitted": true
    },
    "opponent": {
      "id": "uuid2",
      "name": "Bob",
      "score": 50,
      "submitted": true
    }
  }
}
```

---

### `pong`

Keep-alive response.

```json
{
  "event": "pong",
  "data": {}
}
```

---

### `error`

Sent when an error occurs.

```json
{
  "event": "error",
  "data": {
    "message": "Room not found or full"
  }
}
```

---

## HTTP Endpoints

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "rooms": 5
}
```

### `GET /`

API info endpoint.

**Response:**
```json
{
  "name": "Sports Trivia 1v1",
  "version": "0.1.0",
  "websocket": "/ws",
  "health": "/health"
}
```

---

### `GET /api/clubs/{sport}`

Get list of clubs for autocomplete.

**Parameters:**
- `sport`: `nba` or `soccer`

**Response:**
```json
[
  {
    "key": "los-angeles-lakers",
    "display_name": "Los Angeles Lakers",
    "full_name": "Los Angeles Lakers",
    "abbreviation": "LAL",
    "logo": "https://...",
    "badge": "https://..."
  }
]
```

---

### `GET /api/validate-club/{sport}/{club_name}`

Validate a club name with fuzzy matching.

**Parameters:**
- `sport`: `nba` or `soccer`
- `club_name`: Name to validate

**Response (valid):**
```json
{
  "valid": true,
  "normalized_name": "Los Angeles Lakers"
}
```

**Response (invalid):**
```json
{
  "valid": false,
  "error": "Club not found"
}
```
