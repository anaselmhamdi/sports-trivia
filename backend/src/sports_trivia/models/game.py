"""Game state models."""

from enum import Enum

from pydantic import BaseModel


class Sport(str, Enum):
    """Supported sports."""

    SOCCER = "soccer"
    NBA = "nba"


class GamePhase(str, Enum):
    """Game state machine phases."""

    WAITING_FOR_PLAYERS = "waiting_for_players"
    WAITING_FOR_CLUBS = "waiting_for_clubs"
    VALIDATING = "validating"
    GUESSING = "guessing"
    ROUND_END = "round_end"


class Player(BaseModel):
    """A player in the game."""

    id: str
    name: str
    score: int = 0
    submitted_club: str | None = None

    def reset_for_round(self) -> None:
        """Reset player state for a new round."""
        self.submitted_club = None


class GameState(BaseModel):
    """Current state of the game."""

    version: int = 0  # Increment on every mutation for stale client detection
    phase: GamePhase = GamePhase.WAITING_FOR_PLAYERS
    clubs: tuple[str, str] | None = None
    deadline: float | None = None  # Unix timestamp
    winner_id: str | None = None
    winning_answer: str | None = None
    valid_answers: list[str] = []
    valid_answer_count: int = 0

    def increment_version(self) -> int:
        """Increment and return the new version number."""
        self.version += 1
        return self.version

    def reset_for_round(self) -> None:
        """Reset game state for a new round."""
        self.phase = GamePhase.WAITING_FOR_CLUBS
        self.clubs = None
        self.deadline = None
        self.winner_id = None
        self.winning_answer = None
        self.valid_answers = []
        self.valid_answer_count = 0
        self.increment_version()
