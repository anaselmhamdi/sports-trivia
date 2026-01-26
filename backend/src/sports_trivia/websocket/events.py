"""WebSocket event type definitions."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class ClientEvent(str, Enum):
    """Events sent from client to server."""

    CREATE_ROOM = "create_room"
    JOIN_ROOM = "join_room"
    SUBMIT_CLUB = "submit_club"
    SUBMIT_GUESS = "submit_guess"
    PLAY_AGAIN = "play_again"
    LEAVE_ROOM = "leave_room"
    SYNC_STATE = "sync_state"  # Request full state sync (reconnection)
    PING = "ping"  # Keep-alive ping


class ServerEvent(str, Enum):
    """Events sent from server to client."""

    ROOM_CREATED = "room_created"
    ROOM_JOINED = "room_joined"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    CLUB_SUBMITTED = "club_submitted"
    CLUBS_INVALID = "clubs_invalid"
    GUESSING_STARTED = "guessing_started"
    GUESS_RESULT = "guess_result"
    ROUND_ENDED = "round_ended"
    NEW_ROUND = "new_round"
    ERROR = "error"
    STATE_SYNC = "state_sync"  # Full state sync for reconnection
    PONG = "pong"  # Keep-alive pong response


class WebSocketMessage(BaseModel):
    """Base WebSocket message structure."""

    event: str
    data: dict[str, Any] = {}


def create_message(event: ServerEvent, **data: Any) -> dict[str, Any]:
    """Create a server message."""
    return {"event": event.value, "data": data}
