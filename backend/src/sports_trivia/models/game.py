"""Game state models."""

from enum import Enum

from pydantic import BaseModel


class Sport(str, Enum):
    """Supported sports."""

    SOCCER = "soccer"
    NBA = "nba"


class GameMode(str, Enum):
    """Game mode types."""

    CLASSIC = "classic"  # 2 players, each submits a club
    MULTIPLAYER = "multiplayer"  # 2-10 players, shared club pool
    NBA_GRID = "nba_grid"  # 2 players, 3x3 Immaculate Grid tic-tac-toe


class GamePhase(str, Enum):
    """Game state machine phases."""

    WAITING_FOR_PLAYERS = "waiting_for_players"
    WAITING_FOR_CLUBS = "waiting_for_clubs"
    VALIDATING = "validating"
    GUESSING = "guessing"
    ROUND_END = "round_end"


class ClubSubmission(BaseModel):
    """A club submitted to the pool in multiplayer mode."""

    player_id: str
    club_name: str
    submitted_at: float


class Player(BaseModel):
    """A player in the game."""

    id: str
    name: str
    score: int = 0
    submitted_club: str | None = None

    def reset_for_round(self) -> None:
        """Reset player state for a new round."""
        self.submitted_club = None


class GridCell(BaseModel):
    """One cell of the NBA Grid (3x3)."""

    marked_by: str | None = None  # player_id who claimed it
    symbol: str | None = None  # "X" or "O"
    player_name: str | None = None  # the winning guess (canonical name)
    player_image_url: str | None = None


class GridCategory(BaseModel):
    """A row or column category on the NBA Grid."""

    id: str  # stable id e.g. "team_lakers", "award_mvp"
    family: (
        str  # "team" | "award" | "draft" | "decade" | "stat" | "team_count" | "coach" | "champion"
    )
    display_name: str  # human-readable label
    description: str | None = None  # one-line clarification for ambiguous categories
    icon_url: str | None = None  # image path (asset or remote URL)
    icon_kind: str = "text"  # "logo" | "trophy" | "portrait" | "text"
    valid_player_ids: list[int] = []  # precomputed at grid-generation time


class DrawProposal(BaseModel):
    """Pending draw proposal for NBA Grid mode."""

    proposer_id: str
    proposed_at: float  # epoch seconds


class GameState(BaseModel):
    """Current state of the game."""

    version: int = 0  # Increment on every mutation for stale client detection
    phase: GamePhase = GamePhase.WAITING_FOR_PLAYERS
    clubs: tuple[str, str] | None = None  # Classic mode: exactly 2 clubs
    selected_clubs: list[str] = []  # Multiplayer mode: 2-4 selected clubs
    deadline: float | None = None  # Unix timestamp
    winner_id: str | None = None
    winning_answer: str | None = None
    valid_answers: list[str] = []
    valid_answer_count: int = 0

    # Multiplayer mode fields
    club_pool: list[ClubSubmission] = []  # Clubs submitted to shared pool
    clubs_per_round: int = 2  # How many clubs to select (2-4), higher = harder

    # NBA Grid mode fields (only populated when mode == GameMode.NBA_GRID)
    grid: list[list[GridCell]] | None = None  # 3x3 matrix
    row_categories: list[GridCategory] | None = None  # length 3
    col_categories: list[GridCategory] | None = None  # length 3
    current_turn_player_id: str | None = None  # whose turn it is
    player_symbols: dict[str, str] | None = None  # {player_id: "X"|"O"}
    turn_deadline: float | None = None  # epoch when the current turn expires
    draw_proposal: DrawProposal | None = None
    last_draw_decline_at: float | None = None  # cooldown tracker
    end_reason: str | None = None  # "three_in_row" | "board_full" | "draw_accepted"

    def increment_version(self) -> int:
        """Increment and return the new version number."""
        self.version += 1
        return self.version

    def reset_for_round(self, clear_pool: bool = True) -> None:
        """Reset game state for a new round.

        Args:
            clear_pool: If True, also clear the club pool (classic mode).
                       If False, keep pool for instant re-pick (multiplayer).
        """
        self.phase = GamePhase.WAITING_FOR_CLUBS
        self.clubs = None
        self.selected_clubs = []
        self.deadline = None
        self.winner_id = None
        self.winning_answer = None
        self.valid_answers = []
        self.valid_answer_count = 0
        if clear_pool:
            self.club_pool = []
        # Grid-mode fields also cleared on round reset
        self.grid = None
        self.row_categories = None
        self.col_categories = None
        self.current_turn_player_id = None
        self.player_symbols = None
        self.turn_deadline = None
        self.draw_proposal = None
        self.last_draw_decline_at = None
        self.end_reason = None
        self.increment_version()
