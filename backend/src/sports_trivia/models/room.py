"""Room model."""

import asyncio
import threading

from pydantic import BaseModel, ConfigDict, PrivateAttr

from sports_trivia.models.game import GamePhase, GameState, Player, Sport


class Room(BaseModel):
    """A game room containing two players."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: str
    sport: Sport
    players: list[Player] = []
    game_state: GameState = GameState()

    # Runtime-only locks, not serialized
    _lock: asyncio.Lock | None = PrivateAttr(default=None)
    _lock_init: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def get_lock(self) -> asyncio.Lock:
        """Get or create the per-room lock for serializing state mutations."""
        # Use threading lock to safely initialize the asyncio lock
        with self._lock_init:
            if self._lock is None:
                self._lock = asyncio.Lock()
            return self._lock

    def add_player(self, player: Player) -> bool:
        """Add a player to the room. Returns True if successful."""
        if len(self.players) >= 2:
            return False
        if any(p.id == player.id for p in self.players):
            return False
        self.players.append(player)

        # Transition to WAITING_FOR_CLUBS when 2 players join
        if len(self.players) == 2:
            self.game_state.phase = GamePhase.WAITING_FOR_CLUBS
        return True

    def remove_player(self, player_id: str) -> Player | None:
        """Remove a player from the room. Returns the removed player or None."""
        for i, player in enumerate(self.players):
            if player.id == player_id:
                removed = self.players.pop(i)
                # Reset to waiting for players if someone leaves
                if len(self.players) < 2:
                    self.game_state.phase = GamePhase.WAITING_FOR_PLAYERS
                return removed
        return None

    def get_player(self, player_id: str) -> Player | None:
        """Get a player by ID."""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def is_full(self) -> bool:
        """Check if the room has two players."""
        return len(self.players) >= 2

    def is_empty(self) -> bool:
        """Check if the room has no players."""
        return len(self.players) == 0

    def reset_for_round(self) -> None:
        """Reset room state for a new round."""
        self.game_state.reset_for_round()
        for player in self.players:
            player.reset_for_round()
