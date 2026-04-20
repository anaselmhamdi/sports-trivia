"""Game logic and state machine management."""

from __future__ import annotations

import logging
import random
import time
import unicodedata
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from rapidfuzz import fuzz, process

from sports_trivia.config import settings
from sports_trivia.models import (
    ClubSubmission,
    DrawProposal,
    GameMode,
    GamePhase,
    GridCategory,
    GridCell,
    Room,
    Sport,
)

logger = logging.getLogger(__name__)

# Minimum fuzzy match score for player names (higher = stricter)
PLAYER_FUZZY_THRESHOLD = 85

# Maximum retry attempts for selecting clubs with common players
MAX_SELECTION_RETRIES = 5

# NBA Grid tuning
GRID_TURN_SECONDS = 60.0  # fresh budget granted at the start of every turn
GRID_DRAW_COOLDOWN_SECONDS = 10.0
GRID_NBA_IMAGE_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760/{ext_id}.png"

# Back-compat alias for tests that reference the old symbol.
GRID_STARTING_CLOCK_SECONDS = GRID_TURN_SECONDS


def _nba_headshot_url(external_id: str | None) -> str | None:
    """Build the NBA.com headshot URL for a player by external NBA ID."""
    if not external_id:
        return None
    return GRID_NBA_IMAGE_URL.format(ext_id=external_id)


def _category_to_dict(cat: GridCategory) -> dict[str, Any]:
    """Serialize a GridCategory for broadcast (omit the large player-id list)."""
    return {
        "id": cat.id,
        "family": cat.family,
        "display_name": cat.display_name,
        "description": cat.description,
        "icon_url": cat.icon_url,
        "icon_kind": cat.icon_kind,
    }


def _grid_to_dict(grid: list[list[GridCell]]) -> list[list[dict[str, Any]]]:
    """Serialize the 3x3 grid for broadcast."""
    return [
        [
            {
                "marked_by": cell.marked_by,
                "symbol": cell.symbol,
                "player_name": cell.player_name,
                "player_image_url": cell.player_image_url,
            }
            for cell in row
        ]
        for row in grid
    ]


# 8 winning lines on a 3x3 grid: (row, col) triples
_GRID_WIN_LINES: tuple[tuple[tuple[int, int], tuple[int, int], tuple[int, int]], ...] = (
    ((0, 0), (0, 1), (0, 2)),
    ((1, 0), (1, 1), (1, 2)),
    ((2, 0), (2, 1), (2, 2)),
    ((0, 0), (1, 0), (2, 0)),
    ((0, 1), (1, 1), (2, 1)),
    ((0, 2), (1, 2), (2, 2)),
    ((0, 0), (1, 1), (2, 2)),
    ((0, 2), (1, 1), (2, 0)),
)


def strip_accents(text: str) -> str:
    """Remove accents from text for better fuzzy matching.

    Converts "Mbappé" -> "Mbappe", "Müller" -> "Muller", etc.
    """
    # NFD decomposes characters (é -> e + combining accent)
    # Then we filter out the combining characters
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


if TYPE_CHECKING:
    from sports_trivia.services.base import SportDataService


class TransitionResult(Enum):
    """Result of a state transition attempt."""

    SUCCESS = auto()
    INVALID_PHASE = auto()
    ALREADY_SUBMITTED = auto()
    INVALID_CLUB = auto()
    DUPLICATE_CLUB = auto()  # Club already in pool (multiplayer)
    TIME_EXPIRED = auto()
    NO_COMMON_PLAYERS = auto()
    SELECTION_FAILED = auto()  # All retry attempts failed (multiplayer)
    PLAYER_NOT_FOUND = auto()
    NOT_READY = auto()
    NOT_HOST = auto()  # Only host can perform this action
    INSUFFICIENT_CLUBS = auto()  # Not enough clubs in pool


@dataclass
class SubmitClubResult:
    """Result of club submission."""

    status: TransitionResult
    club: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == TransitionResult.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for backwards compatibility."""
        if self.success:
            return {"success": True, "club": self.club}
        return {"success": False, "error": self.error or self.status.name}


@dataclass
class StartGuessingResult:
    """Result of starting guessing phase."""

    status: TransitionResult
    clubs: tuple[str, str] | None = None
    club_info: tuple[dict, dict] | None = None  # Club info with logos
    deadline: float | None = None
    valid_count: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == TransitionResult.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for backwards compatibility."""
        if self.success:
            return {
                "success": True,
                "clubs": self.clubs,
                "club_info": self.club_info,
                "deadline": self.deadline,
                "valid_count": self.valid_count,
            }
        return {"success": False, "error": self.error or self.status.name}


@dataclass
class SubmitGuessResult:
    """Result of guess submission."""

    status: TransitionResult
    correct: bool = False
    player_id: str | None = None
    answer: str | None = None
    guess: str | None = None
    points: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == TransitionResult.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for backwards compatibility."""
        if not self.success:
            return {"success": False, "error": self.error or self.status.name}
        if self.correct:
            return {
                "success": True,
                "correct": True,
                "player_id": self.player_id,
                "answer": self.answer,
                "points": self.points,
            }
        return {
            "success": True,
            "correct": False,
            "player_id": self.player_id,
            "guess": self.guess,
        }


@dataclass
class SubmitPoolResult:
    """Result of submitting a club to the multiplayer pool."""

    status: TransitionResult
    club: str | None = None
    pool_size: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == TransitionResult.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        if self.success:
            return {"success": True, "club": self.club, "pool_size": self.pool_size}
        return {"success": False, "error": self.error or self.status.name}


@dataclass
class SelectClubsResult:
    """Result of selecting clubs from pool for a round."""

    status: TransitionResult
    clubs: list[str] = field(default_factory=list)
    club_info: list[dict] = field(default_factory=list)
    club_submitters: dict[str, str] = field(default_factory=dict)  # club -> player_id
    deadline: float | None = None
    valid_count: int = 0
    fallback_club_count: int | None = None  # If we fell back to fewer clubs
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == TransitionResult.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        if self.success:
            result = {
                "success": True,
                "clubs": self.clubs,
                "club_info": self.club_info,
                "club_submitters": self.club_submitters,
                "deadline": self.deadline,
                "valid_count": self.valid_count,
            }
            if self.fallback_club_count:
                result["fallback_club_count"] = self.fallback_club_count
            return result
        return {"success": False, "error": self.error or self.status.name}


class GameManager:
    """Manages game logic and state transitions."""

    def __init__(self) -> None:
        pass

    def submit_club(self, room: Room, player_id: str, club_name: str) -> dict:
        """
        Submit a club for the round.
        Routes to appropriate handler based on game mode.
        Returns a dict with status and any error message.
        """
        if room.mode == GameMode.MULTIPLAYER:
            result = self._submit_club_to_pool_atomic(room, player_id, club_name)
            return result.to_dict()
        result = self._submit_club_atomic(room, player_id, club_name)
        return result.to_dict()

    def _submit_club_to_pool_atomic(
        self, room: Room, player_id: str, club_name: str
    ) -> SubmitPoolResult:
        """Submit a club to the multiplayer pool."""
        # Validate phase
        if room.game_state.phase != GamePhase.WAITING_FOR_CLUBS:
            return SubmitPoolResult(
                status=TransitionResult.INVALID_PHASE,
                error="Not in club submission phase",
            )

        player = room.get_player(player_id)
        if player is None:
            return SubmitPoolResult(
                status=TransitionResult.PLAYER_NOT_FOUND,
                error="Player not in room",
            )

        # Check if player already submitted
        if any(s.player_id == player_id for s in room.game_state.club_pool):
            return SubmitPoolResult(
                status=TransitionResult.ALREADY_SUBMITTED,
                error="Already submitted a club",
            )

        # Validate club exists
        data_service = self._get_data_service(room.sport)
        if not data_service.validate_club(club_name):
            return SubmitPoolResult(
                status=TransitionResult.INVALID_CLUB,
                error=f"Club '{club_name}' not found",
            )

        # Normalize the club name
        normalized_club = data_service.normalize_club_name(club_name)

        # Check for duplicate club in pool
        if any(s.club_name == normalized_club for s in room.game_state.club_pool):
            return SubmitPoolResult(
                status=TransitionResult.DUPLICATE_CLUB,
                error=f"Club '{normalized_club}' already in pool",
            )

        # Add to pool
        submission = ClubSubmission(
            player_id=player_id,
            club_name=normalized_club,
            submitted_at=time.time(),
        )
        room.game_state.club_pool.append(submission)

        # Also set player.submitted_club for consistency
        player.submitted_club = normalized_club
        room.game_state.increment_version()

        return SubmitPoolResult(
            status=TransitionResult.SUCCESS,
            club=normalized_club,
            pool_size=len(room.game_state.club_pool),
        )

    def _submit_club_atomic(self, room: Room, player_id: str, club_name: str) -> SubmitClubResult:
        """Atomic club submission with typed result."""
        # Validate phase
        if room.game_state.phase != GamePhase.WAITING_FOR_CLUBS:
            return SubmitClubResult(
                status=TransitionResult.INVALID_PHASE,
                error="Not in club submission phase",
            )

        player = room.get_player(player_id)
        if player is None:
            return SubmitClubResult(
                status=TransitionResult.PLAYER_NOT_FOUND,
                error="Player not in room",
            )

        if player.submitted_club is not None:
            return SubmitClubResult(
                status=TransitionResult.ALREADY_SUBMITTED,
                error="Already submitted a club",
            )

        # Validate club exists
        data_service = self._get_data_service(room.sport)
        if not data_service.validate_club(club_name):
            return SubmitClubResult(
                status=TransitionResult.INVALID_CLUB,
                error=f"Club '{club_name}' not found",
            )

        # Normalize the club name and assign atomically
        normalized_club = data_service.normalize_club_name(club_name)
        player.submitted_club = normalized_club
        room.game_state.increment_version()

        return SubmitClubResult(status=TransitionResult.SUCCESS, club=normalized_club)

    def check_clubs_ready(self, room: Room) -> bool:
        """Check if clubs are ready to start guessing (classic mode only)."""
        if room.mode == GameMode.MULTIPLAYER:
            # Multiplayer uses pool, not player submissions
            return False
        if len(room.players) != 2:
            return False
        return all(p.submitted_club is not None for p in room.players)

    def start_game(self, room: Room, player_id: str) -> dict:
        """Start a multiplayer game (host only). Transitions from WAITING_FOR_PLAYERS to WAITING_FOR_CLUBS."""
        if room.mode != GameMode.MULTIPLAYER:
            return {"success": False, "error": "start_game only valid for multiplayer"}

        if player_id != room.host_id:
            return {"success": False, "error": "Only host can start the game"}

        if room.game_state.phase != GamePhase.WAITING_FOR_PLAYERS:
            return {"success": False, "error": "Game already started"}

        if len(room.players) < 2:
            return {"success": False, "error": "Need at least 2 players"}

        room.game_state.phase = GamePhase.WAITING_FOR_CLUBS
        room.game_state.increment_version()

        return {"success": True, "phase": room.game_state.phase.value}

    def start_round(self, room: Room, player_id: str, clubs_per_round: int = 2) -> dict:
        """Start a round in multiplayer mode by selecting clubs from pool."""
        if room.mode != GameMode.MULTIPLAYER:
            return {"success": False, "error": "start_round only valid for multiplayer"}

        if player_id != room.host_id:
            return {"success": False, "error": "Only host can start the round"}

        result = self._select_clubs_from_pool_atomic(room, clubs_per_round)
        return result.to_dict()

    def _select_clubs_from_pool_atomic(self, room: Room, clubs_per_round: int) -> SelectClubsResult:
        """Select clubs from pool and start guessing phase."""
        # Validate phase
        if room.game_state.phase != GamePhase.WAITING_FOR_CLUBS:
            return SelectClubsResult(
                status=TransitionResult.INVALID_PHASE,
                error="Not in club submission phase",
            )

        # Validate clubs_per_round (2-4)
        clubs_per_round = max(2, min(4, clubs_per_round))

        pool = room.game_state.club_pool
        pool_size = len(pool)

        # Cap clubs_per_round by pool size
        actual_club_count = min(clubs_per_round, pool_size)

        if actual_club_count < 2:
            return SelectClubsResult(
                status=TransitionResult.INSUFFICIENT_CLUBS,
                error=f"Need at least 2 clubs in pool (have {pool_size})",
            )

        data_service = self._get_data_service(room.sport)

        # Try to find clubs with common players
        # If requested club_count fails, fall back to fewer clubs
        for target_count in range(actual_club_count, 1, -1):
            result = self._try_select_clubs(pool, target_count, data_service, room, clubs_per_round)
            if result:
                return result

        # All attempts failed
        return SelectClubsResult(
            status=TransitionResult.SELECTION_FAILED,
            error="Could not find clubs with common players. Need more diverse club submissions.",
        )

    def _try_select_clubs(
        self,
        pool: list[ClubSubmission],
        target_count: int,
        data_service: Any,
        room: Room,
        original_request: int,
    ) -> SelectClubsResult | None:
        """Try to select clubs from pool with common players. Returns None if failed."""
        pool_clubs = [s.club_name for s in pool]

        # Build mapping of club -> player_id
        club_to_player = {s.club_name: s.player_id for s in pool}

        # Try random combinations up to MAX_SELECTION_RETRIES times
        tried_combinations: set[tuple[str, ...]] = set()

        for _ in range(MAX_SELECTION_RETRIES):
            # Select random clubs
            if len(pool_clubs) == target_count:
                selected = pool_clubs[:]
            else:
                selected = random.sample(pool_clubs, target_count)

            # Check if we've already tried this combination
            combo_key = tuple(sorted(selected))
            if combo_key in tried_combinations:
                continue
            tried_combinations.add(combo_key)

            # Check for common players
            common_players = data_service.find_common_players_multi(selected)

            if common_players:
                # Success! Transition to guessing phase
                club_info = [
                    data_service.get_club_info(club) or {"full_name": club} for club in selected
                ]
                club_submitters = {club: club_to_player[club] for club in selected}

                room.game_state.phase = GamePhase.GUESSING
                room.game_state.selected_clubs = selected
                room.game_state.clubs = (selected[0], selected[1]) if len(selected) >= 2 else None
                room.game_state.clubs_per_round = target_count
                room.game_state.valid_answers = common_players
                room.game_state.valid_answer_count = len(common_players)
                room.game_state.deadline = time.time() + settings.default_timer_seconds
                room.game_state.increment_version()

                result = SelectClubsResult(
                    status=TransitionResult.SUCCESS,
                    clubs=selected,
                    club_info=club_info,
                    club_submitters=club_submitters,
                    deadline=room.game_state.deadline,
                    valid_count=len(common_players),
                )

                # Indicate if we fell back to fewer clubs
                if target_count < original_request:
                    result.fallback_club_count = target_count

                return result

        return None

    def start_guessing_phase(self, room: Room) -> dict:
        """
        Validate clubs and start the guessing phase.
        For classic mode: uses player submissions.
        For multiplayer: should use start_round() instead.
        Returns info about the round or error if no common players.
        """
        if room.mode == GameMode.MULTIPLAYER:
            # Multiplayer should use start_round() which selects from pool
            return {"success": False, "error": "Use start_round for multiplayer mode"}
        result = self._start_guessing_atomic(room)
        return result.to_dict()

    def _start_guessing_atomic(self, room: Room) -> StartGuessingResult:
        """Atomically transition to guessing phase if ready (classic mode)."""
        # Validate phase
        if room.game_state.phase != GamePhase.WAITING_FOR_CLUBS:
            return StartGuessingResult(
                status=TransitionResult.INVALID_PHASE,
                error="Not ready to start guessing",
            )

        if not self.check_clubs_ready(room):
            return StartGuessingResult(
                status=TransitionResult.NOT_READY,
                error="Both players must submit clubs",
            )

        club1 = room.players[0].submitted_club
        club2 = room.players[1].submitted_club

        if club1 is None or club2 is None:
            return StartGuessingResult(
                status=TransitionResult.NOT_READY,
                error="Missing club submissions",
            )

        # Find common players
        data_service = self._get_data_service(room.sport)
        common_players = data_service.find_common_players(club1, club2)

        if not common_players:
            # Reset submissions and ask for new clubs
            for player in room.players:
                player.submitted_club = None
            room.game_state.increment_version()  # State changed, increment version
            return StartGuessingResult(
                status=TransitionResult.NO_COMMON_PLAYERS,
                error=f"No players found who played for both {club1} and {club2}",
            )

        # Fetch club info for logos
        club1_info = data_service.get_club_info(club1) or {"full_name": club1}
        club2_info = data_service.get_club_info(club2) or {"full_name": club2}

        # Atomic transition to guessing phase
        room.game_state.phase = GamePhase.GUESSING
        room.game_state.clubs = (club1, club2)
        room.game_state.selected_clubs = [club1, club2]
        room.game_state.valid_answers = common_players
        room.game_state.valid_answer_count = len(common_players)
        room.game_state.deadline = time.time() + settings.default_timer_seconds
        room.game_state.increment_version()

        return StartGuessingResult(
            status=TransitionResult.SUCCESS,
            clubs=(club1, club2),
            club_info=(club1_info, club2_info),
            deadline=room.game_state.deadline,
            valid_count=len(common_players),
        )

    def submit_guess(self, room: Room, player_id: str, guess: str) -> dict:
        """
        Submit a player name guess.
        Returns result including whether the guess was correct.
        """
        result = self._submit_guess_atomic(room, player_id, guess)
        return result.to_dict()

    def _submit_guess_atomic(self, room: Room, player_id: str, guess: str) -> SubmitGuessResult:
        """Atomic guess submission with typed result."""
        # Validate phase
        if room.game_state.phase != GamePhase.GUESSING:
            return SubmitGuessResult(
                status=TransitionResult.INVALID_PHASE,
                error="Not in guessing phase",
            )

        player = room.get_player(player_id)
        if player is None:
            return SubmitGuessResult(
                status=TransitionResult.PLAYER_NOT_FOUND,
                error="Player not in room",
            )

        # Check if time expired
        if room.game_state.deadline and time.time() > room.game_state.deadline:
            return SubmitGuessResult(
                status=TransitionResult.TIME_EXPIRED,
                error="Time expired",
            )

        # Normalize and check the guess
        data_service = self._get_data_service(room.sport)
        normalized_guess = data_service.normalize_player_name(guess)

        # Check against valid answers with fuzzy matching
        is_correct, matched_answer = self._match_player_name(
            normalized_guess, room.game_state.valid_answers
        )

        if is_correct:
            # Calculate score based on time remaining
            time_remaining = max(0, room.game_state.deadline - time.time())
            time_elapsed = settings.default_timer_seconds - time_remaining
            points = max(1, settings.max_points_per_round - int(time_elapsed))

            # Atomic state transition
            player.score += points
            room.game_state.phase = GamePhase.ROUND_END
            room.game_state.winner_id = player_id
            room.game_state.winning_answer = matched_answer or normalized_guess
            room.game_state.increment_version()

            return SubmitGuessResult(
                status=TransitionResult.SUCCESS,
                correct=True,
                player_id=player_id,
                answer=matched_answer or normalized_guess,
                points=points,
            )

        return SubmitGuessResult(
            status=TransitionResult.SUCCESS,
            correct=False,
            player_id=player_id,
            guess=normalized_guess,
        )

    def end_round_timeout(self, room: Room) -> dict:
        """End the round due to timeout (no winner)."""
        if room.game_state.phase != GamePhase.GUESSING:
            return {"success": False, "error": "Not in guessing phase"}

        room.game_state.phase = GamePhase.ROUND_END
        room.game_state.winner_id = None
        room.game_state.winning_answer = None
        room.game_state.increment_version()

        return {
            "success": True,
            "winner_id": None,
            "valid_answers": room.game_state.valid_answers,
        }

    def start_new_round(self, room: Room, player_id: str | None = None) -> dict:
        """Start a new round (play again).

        For classic mode: resets to WAITING_FOR_CLUBS and requires new submissions.
        For multiplayer: keeps pool and immediately selects new clubs (instant re-pick).
        For NBA Grid: regenerates the grid and starts a fresh game (host only).
        """
        if room.game_state.phase != GamePhase.ROUND_END:
            return {"success": False, "error": "Round not ended"}

        if room.mode == GameMode.MULTIPLAYER:
            # Multiplayer: keep pool, reset game state, immediately select new clubs
            if player_id and player_id != room.host_id:
                return {"success": False, "error": "Only host can start new round"}

            # Reset game state but keep pool
            room.reset_for_round(clear_pool=False)

            # Immediately select new clubs and start guessing
            clubs_per_round = room.game_state.clubs_per_round or 2
            result = self._select_clubs_from_pool_atomic(room, clubs_per_round)
            return result.to_dict()

        if room.mode == GameMode.NBA_GRID:
            if player_id and player_id != room.host_id:
                return {"success": False, "error": "Only host can start new round"}
            # Reset grid state, then regenerate. start_grid_game requires
            # WAITING_FOR_PLAYERS, so reset_for_round drops us there.
            room.reset_for_round(clear_pool=True)
            room.game_state.phase = GamePhase.WAITING_FOR_PLAYERS
            return self.start_grid_game(room, room.host_id or "")

        # Classic mode: reset everything
        room.reset_for_round(clear_pool=True)
        return {"success": True, "phase": room.game_state.phase.value}

    def _get_data_service(self, sport: Sport) -> SportDataService:
        """Get the appropriate data service for the sport."""
        # Import here to avoid circular import
        from sports_trivia.services import get_service

        return get_service(sport)

    # ------------------------------------------------------------------
    # NBA Grid mode
    # ------------------------------------------------------------------

    def start_grid_game(self, room: Room, player_id: str) -> dict[str, Any]:
        """Generate a grid, assign symbols, pick first turn, start clocks.

        Host only. Requires exactly 2 players in NBA_GRID mode.
        """
        if room.mode != GameMode.NBA_GRID:
            return {"success": False, "error": "start_grid_game only valid for NBA Grid mode"}
        if player_id != room.host_id:
            return {"success": False, "error": "Only host can start the game"}
        if room.sport != Sport.NBA:
            return {"success": False, "error": "NBA Grid currently supports NBA only"}
        if len(room.players) != 2:
            return {"success": False, "error": "Need exactly 2 players"}
        if room.game_state.phase != GamePhase.WAITING_FOR_PLAYERS:
            return {"success": False, "error": "Game already started"}

        # Generate grid via fresh DB session.
        from sports_trivia.db import get_session
        from sports_trivia.services.grid_generator import (
            GridGenerationError,
            generate_grid,
        )

        session = get_session()
        try:
            try:
                rows, cols = generate_grid(session)
            except GridGenerationError as e:
                logger.exception("Grid generation failed")
                return {"success": False, "error": str(e)}
        finally:
            session.close()

        # Initialize 3x3 grid of empty cells
        grid = [[GridCell() for _ in range(3)] for _ in range(3)]

        # Host = X, opponent = O
        host = next((p for p in room.players if p.id == room.host_id), room.players[0])
        opp = next(p for p in room.players if p.id != host.id)
        symbols = {host.id: "X", opp.id: "O"}

        # Random first turn
        first_turn = random.choice([host.id, opp.id])

        now = time.time()
        turn_deadline = now + GRID_TURN_SECONDS

        gs = room.game_state
        gs.phase = GamePhase.GUESSING
        gs.grid = grid
        gs.row_categories = rows
        gs.col_categories = cols
        gs.current_turn_player_id = first_turn
        gs.player_symbols = symbols
        gs.turn_deadline = turn_deadline
        gs.draw_proposal = None
        gs.last_draw_decline_at = None
        gs.end_reason = None
        gs.winner_id = None
        gs.increment_version()

        return {
            "success": True,
            "grid": _grid_to_dict(grid),
            "row_categories": [_category_to_dict(c) for c in rows],
            "col_categories": [_category_to_dict(c) for c in cols],
            "player_symbols": symbols,
            "current_turn_player_id": first_turn,
            "turn_deadline": turn_deadline,
        }

    def submit_grid_guess(
        self,
        room: Room,
        player_id: str,
        row: int,
        col: int,
        guess: str,
    ) -> dict[str, Any]:
        """Attempt to claim cell (row, col) with `guess`."""
        gs = room.game_state

        if room.mode != GameMode.NBA_GRID or gs.phase != GamePhase.GUESSING:
            return {"success": False, "error": "Not in an active grid game"}
        if gs.current_turn_player_id != player_id:
            return {"success": False, "error": "Not your turn"}
        if not (0 <= row < 3 and 0 <= col < 3):
            return {"success": False, "error": "Invalid cell coordinates"}
        assert (
            gs.grid is not None and gs.row_categories is not None and gs.col_categories is not None
        )
        if gs.grid[row][col].marked_by is not None:
            return {"success": False, "error": "Cell already marked"}

        # Build the intersection of valid player_ids for this cell
        row_cat = gs.row_categories[row]
        col_cat = gs.col_categories[col]
        intersect = set(row_cat.valid_player_ids).intersection(col_cat.valid_player_ids)
        if not intersect:
            # Shouldn't happen — grid generator enforces min_answers — but be defensive.
            self._grid_swap_turn(room)
            return {
                "success": True,
                "correct": False,
                "row": row,
                "col": col,
                "guess": guess,
                "turn_deadline": gs.turn_deadline,
                "next_turn": gs.current_turn_player_id,
            }

        # Resolve names for the intersection via a fresh session.
        from sports_trivia.db import Player as DBPlayer
        from sports_trivia.db import get_session

        session = get_session()
        try:
            db_players = session.query(DBPlayer).filter(DBPlayer.id.in_(list(intersect))).all()
            candidates = [
                {"id": p.id, "name": p.name, "external_id": p.external_id} for p in db_players
            ]
        finally:
            session.close()

        names = [c["name"] for c in candidates]
        is_match, matched_name = self._match_player_name(guess, names)

        if not is_match:
            self._grid_swap_turn(room)
            return {
                "success": True,
                "correct": False,
                "row": row,
                "col": col,
                "guess": guess,
                "turn_deadline": gs.turn_deadline,
                "next_turn": gs.current_turn_player_id,
            }

        # Correct — mark the cell, check for win.
        matched = next((c for c in candidates if c["name"] == matched_name), None)
        image_url = _nba_headshot_url(matched["external_id"]) if matched else None
        symbol = (gs.player_symbols or {}).get(player_id) or "?"
        cell = gs.grid[row][col]
        cell.marked_by = player_id
        cell.symbol = symbol
        cell.player_name = matched_name
        cell.player_image_url = image_url

        # Win / draw checks
        winner = self._grid_check_winner(room)
        if winner is not None:
            return self._grid_end_three_in_row(room, winner, row, col, matched_name, image_url)
        if self._grid_board_full(room):
            return self._grid_end_board_full(room, row, col, matched_name, image_url)

        self._grid_swap_turn(room)
        return {
            "success": True,
            "correct": True,
            "row": row,
            "col": col,
            "player_id": player_id,
            "symbol": symbol,
            "player_name": matched_name,
            "player_image_url": image_url,
            "turn_deadline": gs.turn_deadline,
            "next_turn": gs.current_turn_player_id,
        }

    def skip_grid_turn(self, room: Room, player_id: str) -> dict[str, Any]:
        """Player voluntarily passes their turn. Opponent gets a fresh 60s."""
        gs = room.game_state
        if room.mode != GameMode.NBA_GRID or gs.phase != GamePhase.GUESSING:
            return {"success": False, "error": "Not in an active grid game"}
        if gs.current_turn_player_id != player_id:
            return {"success": False, "error": "Not your turn"}

        self._grid_swap_turn(room)
        return {
            "success": True,
            "reason": "skip",
            "player_id": player_id,
            "turn_deadline": gs.turn_deadline,
            "next_turn": gs.current_turn_player_id,
        }

    def propose_grid_draw(self, room: Room, player_id: str) -> dict[str, Any]:
        """Open a draw proposal. Opponent must accept/decline."""
        gs = room.game_state
        if room.mode != GameMode.NBA_GRID or gs.phase != GamePhase.GUESSING:
            return {"success": False, "error": "Not in an active grid game"}
        if room.get_player(player_id) is None:
            return {"success": False, "error": "Player not in room"}
        if gs.draw_proposal is not None:
            return {"success": False, "error": "A draw proposal is already pending"}

        now = time.time()
        if gs.last_draw_decline_at is not None:
            since = now - gs.last_draw_decline_at
            if since < GRID_DRAW_COOLDOWN_SECONDS:
                remaining = GRID_DRAW_COOLDOWN_SECONDS - since
                return {
                    "success": False,
                    "error": f"Draw proposals on cooldown ({remaining:.0f}s)",
                }

        gs.draw_proposal = DrawProposal(proposer_id=player_id, proposed_at=now)
        gs.increment_version()
        return {"success": True, "proposer_id": player_id}

    def respond_grid_draw(self, room: Room, player_id: str, accept: bool) -> dict[str, Any]:
        """Accept/decline a pending draw. Accept ends game as a draw."""
        gs = room.game_state
        if room.mode != GameMode.NBA_GRID or gs.phase != GamePhase.GUESSING:
            return {"success": False, "error": "Not in an active grid game"}
        if gs.draw_proposal is None:
            return {"success": False, "error": "No pending draw proposal"}
        if gs.draw_proposal.proposer_id == player_id:
            return {"success": False, "error": "You cannot respond to your own proposal"}

        if accept:
            gs.phase = GamePhase.ROUND_END
            gs.end_reason = "draw_accepted"
            gs.winner_id = None
            gs.draw_proposal = None
            gs.increment_version()
            return {
                "success": True,
                "accepted": True,
                "ended": True,
                "end_reason": "draw_accepted",
                "winner_id": None,
            }

        gs.draw_proposal = None
        gs.last_draw_decline_at = time.time()
        gs.increment_version()
        return {"success": True, "accepted": False, "ended": False}

    def grid_timer_expired(self, room: Room, expired_player_id: str) -> dict[str, Any]:
        """Called by the background watcher when the per-turn 60s clock hits 0.

        Treated as an auto-skip — the turn passes to the opponent with a fresh
        60s budget. The game does NOT end on timer expiry; only 3-in-a-row,
        board-full, or a mutually accepted draw end the game.
        """
        gs = room.game_state
        if room.mode != GameMode.NBA_GRID or gs.phase != GamePhase.GUESSING:
            return {"success": False, "error": "Not in active grid game"}
        if gs.current_turn_player_id != expired_player_id:
            # Turn already moved (e.g. a guess arrived just before the timer).
            return {"success": False, "error": "Turn already advanced"}

        self._grid_swap_turn(room)
        return {
            "success": True,
            "reason": "timeout",
            "player_id": expired_player_id,
            "turn_deadline": gs.turn_deadline,
            "next_turn": gs.current_turn_player_id,
        }

    # Back-compat alias in case older handlers still reference the name.
    grid_clock_expired = grid_timer_expired

    # ---- internal grid helpers ----

    def _grid_swap_turn(self, room: Room) -> None:
        """Hand the turn to the opponent and grant a fresh 60s budget."""
        gs = room.game_state
        if gs.current_turn_player_id is None:
            return
        other = next((p.id for p in room.players if p.id != gs.current_turn_player_id), None)
        if other is None:
            return
        gs.current_turn_player_id = other
        gs.turn_deadline = time.time() + GRID_TURN_SECONDS
        gs.increment_version()

    def _grid_check_winner(self, room: Room) -> str | None:
        """Return the player_id that owns any 3-in-a-row, or None."""
        gs = room.game_state
        if gs.grid is None:
            return None
        for line in _GRID_WIN_LINES:
            owners = {gs.grid[r][c].marked_by for r, c in line}
            if len(owners) == 1 and None not in owners:
                return next(iter(owners))
        return None

    def _grid_board_full(self, room: Room) -> bool:
        gs = room.game_state
        if gs.grid is None:
            return False
        return all(cell.marked_by is not None for row in gs.grid for cell in row)

    def _grid_end_three_in_row(
        self,
        room: Room,
        winner_id: str,
        last_row: int,
        last_col: int,
        player_name: str,
        image_url: str | None,
    ) -> dict[str, Any]:
        gs = room.game_state
        gs.phase = GamePhase.ROUND_END
        gs.winner_id = winner_id
        gs.end_reason = "three_in_row"
        winning_player = room.get_player(winner_id)
        if winning_player is not None:
            winning_player.score += 1
        gs.increment_version()
        return {
            "success": True,
            "correct": True,
            "row": last_row,
            "col": last_col,
            "player_id": winner_id,
            "symbol": (gs.player_symbols or {}).get(winner_id),
            "player_name": player_name,
            "player_image_url": image_url,
            "turn_deadline": gs.turn_deadline,
            "game_ended": True,
            "end_reason": "three_in_row",
            "winner_id": winner_id,
        }

    def _grid_end_board_full(
        self,
        room: Room,
        last_row: int,
        last_col: int,
        player_name: str,
        image_url: str | None,
    ) -> dict[str, Any]:
        """Board full with no 3-in-a-row → DRAW."""
        gs = room.game_state
        gs.phase = GamePhase.ROUND_END
        gs.winner_id = None
        gs.end_reason = "board_full"
        gs.increment_version()
        return {
            "success": True,
            "correct": True,
            "row": last_row,
            "col": last_col,
            "player_id": gs.current_turn_player_id,
            "symbol": (gs.player_symbols or {}).get(gs.current_turn_player_id or "")
            if gs.current_turn_player_id
            else None,
            "player_name": player_name,
            "player_image_url": image_url,
            "turn_deadline": gs.turn_deadline,
            "game_ended": True,
            "end_reason": "board_full",
            "winner_id": None,
        }

    def _match_player_name(self, guess: str, valid_answers: list[str]) -> tuple[bool, str | None]:
        """
        Match a guess against valid answers with fuzzy matching.
        Returns (is_match, matched_full_name).

        Matching rules (in order):
        1. Exact match (case-insensitive, accent-insensitive): "Kylian Mbappe" == "Kylian Mbappé"
        2. Last name match: "Mbappe" == "Kylian Mbappé"
        3. Single-name players: "Neymar" == "Neymar"
        4. Fuzzy match for typos: "Mbape" ~= "Mbappe"

        First name only does NOT match (too easy).
        """
        # Normalize: lowercase and strip accents for comparison
        guess_normalized = strip_accents(guess.lower().strip())

        for answer in valid_answers:
            answer_normalized = strip_accents(answer.lower())
            name_parts = answer_normalized.split()

            # Exact match (accent-insensitive)
            if guess_normalized == answer_normalized:
                return True, answer

            # Single-word guess
            if len(guess_normalized.split()) == 1 and name_parts:
                # Last name match (most common way to refer to players)
                if guess_normalized == name_parts[-1]:
                    return True, answer

                # Single-name player (e.g., "Neymar", "Kaka", "Ronaldinho")
                if len(name_parts) == 1 and guess_normalized == name_parts[0]:
                    return True, answer

            # Multi-word guess containing last name
            # e.g., "Cristiano Ronaldo" matches if last name matches
            guess_parts = guess_normalized.split()
            if len(guess_parts) > 1 and guess_parts[-1] == name_parts[-1]:
                return True, answer

        # Fallback: fuzzy matching for typos (also accent-insensitive)
        # Build candidates: full names and last names
        candidates = []
        for answer in valid_answers:
            answer_normalized = strip_accents(answer.lower())
            candidates.append((answer_normalized, answer))
            # Also add last name as candidate
            name_parts = answer_normalized.split()
            if len(name_parts) > 1:
                candidates.append((name_parts[-1], answer))

        if candidates:
            names = [c[0] for c in candidates]
            result = process.extractOne(
                guess_normalized,
                names,
                scorer=fuzz.WRatio,
                score_cutoff=PLAYER_FUZZY_THRESHOLD,
            )
            if result:
                matched_name, score, index = result
                matched_answer = candidates[index][1]
                logger.info(
                    f"Fuzzy matched player '{guess}' -> '{matched_answer}' (score: {score})"
                )
                return True, matched_answer

        return False, None
