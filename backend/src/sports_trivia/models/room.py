"""Room model."""

import asyncio
import threading

from pydantic import BaseModel, ConfigDict, PrivateAttr

from sports_trivia.models.game import GameMode, GamePhase, GameState, Player, Sport


class Room(BaseModel):
    """A game room containing players."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: str
    sport: Sport
    mode: GameMode = GameMode.CLASSIC
    max_players: int = 2  # 2 for classic, 2-10 for multiplayer
    host_id: str | None = None  # Player who created the room
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
        if len(self.players) >= self.max_players:
            return False
        if any(p.id == player.id for p in self.players):
            return False
        self.players.append(player)

        # Only auto-transition for CLASSIC mode when 2 players join
        if self.mode == GameMode.CLASSIC and len(self.players) == 2:
            self.game_state.phase = GamePhase.WAITING_FOR_CLUBS
        return True

    def remove_player(self, player_id: str) -> Player | None:
        """Remove a player from the room. Returns the removed player or None."""
        for i, player in enumerate(self.players):
            if player.id == player_id:
                removed = self.players.pop(i)

                # In multiplayer, remove player's club from pool
                if self.mode == GameMode.MULTIPLAYER:
                    self.game_state.club_pool = [
                        s for s in self.game_state.club_pool if s.player_id != player_id
                    ]

                # Reset to waiting for players if someone leaves (classic needs 2)
                if self.mode == GameMode.CLASSIC and len(self.players) < 2:
                    self.game_state.phase = GamePhase.WAITING_FOR_PLAYERS

                # Transfer host if host leaves (multiplayer)
                if self.host_id == player_id and self.players:
                    self.host_id = self.players[0].id

                return removed
        return None

    def get_player(self, player_id: str) -> Player | None:
        """Get a player by ID."""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def is_full(self) -> bool:
        """Check if the room has reached max players."""
        return len(self.players) >= self.max_players

    def is_empty(self) -> bool:
        """Check if the room has no players."""
        return len(self.players) == 0

    def reset_for_round(self, clear_pool: bool = True) -> None:
        """Reset room state for a new round.

        Args:
            clear_pool: If True, also clear the club pool (classic mode).
                       If False, keep pool for instant re-pick (multiplayer).
        """
        self.game_state.reset_for_round(clear_pool)
        if clear_pool:
            for player in self.players:
                player.reset_for_round()
