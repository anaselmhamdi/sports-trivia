"""Room lifecycle management."""

import asyncio
import contextlib
import logging
import random
import string
from datetime import datetime, timedelta

from sports_trivia.models import GameState, Player, Room, Sport

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages room creation, joining, and lifecycle."""

    # Room TTL configuration
    ROOM_TTL_MINUTES: int = 30
    CLEANUP_INTERVAL_SECONDS: int = 60

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._room_activity: dict[str, datetime] = {}
        self._cleanup_task: asyncio.Task | None = None

    def _generate_room_code(self, length: int = 4) -> str:
        """Generate a unique 4-letter room code."""
        while True:
            code = "".join(random.choices(string.ascii_uppercase, k=length))
            if code not in self._rooms:
                return code

    def create_room(self, player_id: str, player_name: str, sport: Sport) -> Room:
        """Create a new room and add the first player."""
        code = self._generate_room_code()
        room = Room(code=code, sport=sport, game_state=GameState())
        player = Player(id=player_id, name=player_name)
        room.add_player(player)
        self._rooms[code] = room
        self.touch_room(code)
        return room

    def join_room(self, room_code: str, player_id: str, player_name: str) -> Room | None:
        """Join an existing room. Returns None if room doesn't exist or is full."""
        room = self._rooms.get(room_code)
        if room is None:
            return None
        if room.is_full():
            return None

        player = Player(id=player_id, name=player_name)
        if not room.add_player(player):
            return None
        self.touch_room(room_code)
        return room

    def leave_room(self, room_code: str, player_id: str) -> tuple[Room | None, Player | None]:
        """Remove a player from a room. Returns (room, removed_player) or (None, None)."""
        room = self._rooms.get(room_code)
        if room is None:
            return None, None

        removed_player = room.remove_player(player_id)
        if removed_player is None:
            return None, None

        # Clean up empty rooms
        if room.is_empty():
            del self._rooms[room_code]
            self._room_activity.pop(room_code, None)
            return None, removed_player

        self.touch_room(room_code)
        return room, removed_player

    def get_room(self, room_code: str) -> Room | None:
        """Get a room by code."""
        return self._rooms.get(room_code)

    def get_room_for_player(self, player_id: str) -> Room | None:
        """Find the room a player is in."""
        for room in self._rooms.values():
            if room.get_player(player_id) is not None:
                return room
        return None

    def room_exists(self, room_code: str) -> bool:
        """Check if a room exists."""
        return room_code in self._rooms

    @property
    def room_count(self) -> int:
        """Get the total number of active rooms."""
        return len(self._rooms)

    # =========================================================================
    # Room Activity Tracking & Cleanup
    # =========================================================================

    def touch_room(self, room_code: str) -> None:
        """Update last activity timestamp for a room."""
        self._room_activity[room_code] = datetime.now()

    def get_room_last_activity(self, room_code: str) -> datetime | None:
        """Get the last activity timestamp for a room."""
        return self._room_activity.get(room_code)

    async def start_cleanup_task(self) -> None:
        """Start background cleanup of inactive rooms."""
        if self._cleanup_task is not None:
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Room cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
            logger.info("Room cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop that periodically cleans up inactive rooms."""
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_inactive_rooms()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_inactive_rooms(self) -> None:
        """Remove rooms that have been inactive beyond TTL."""
        now = datetime.now()
        ttl = timedelta(minutes=self.ROOM_TTL_MINUTES)
        expired: list[str] = []

        for room_code, last_activity in self._room_activity.items():
            if now - last_activity > ttl:
                expired.append(room_code)

        for room_code in expired:
            logger.info(f"Cleaning up inactive room: {room_code}")
            # Use pop() for safety in case dicts are out of sync
            self._rooms.pop(room_code, None)
            self._room_activity.pop(room_code, None)

        if expired:
            logger.info(f"Cleaned up {len(expired)} inactive rooms")
