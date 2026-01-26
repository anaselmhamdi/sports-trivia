"""Game logic and state machine management."""

from __future__ import annotations

import logging
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from rapidfuzz import fuzz, process

from sports_trivia.config import settings
from sports_trivia.models import GamePhase, Room, Sport

logger = logging.getLogger(__name__)

# Minimum fuzzy match score for player names (higher = stricter)
PLAYER_FUZZY_THRESHOLD = 85


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
    TIME_EXPIRED = auto()
    NO_COMMON_PLAYERS = auto()
    PLAYER_NOT_FOUND = auto()
    NOT_READY = auto()


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


class GameManager:
    """Manages game logic and state transitions."""

    def __init__(self) -> None:
        pass

    def submit_club(self, room: Room, player_id: str, club_name: str) -> dict:
        """
        Submit a club for the round.
        Returns a dict with status and any error message.
        """
        result = self._submit_club_atomic(room, player_id, club_name)
        return result.to_dict()

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
        """Check if both players have submitted clubs."""
        if len(room.players) != 2:
            return False
        return all(p.submitted_club is not None for p in room.players)

    def start_guessing_phase(self, room: Room) -> dict:
        """
        Validate clubs and start the guessing phase.
        Returns info about the round or error if no common players.
        """
        result = self._start_guessing_atomic(room)
        return result.to_dict()

    def _start_guessing_atomic(self, room: Room) -> StartGuessingResult:
        """Atomically transition to guessing phase if ready."""
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

    def start_new_round(self, room: Room) -> dict:
        """Start a new round (play again)."""
        if room.game_state.phase != GamePhase.ROUND_END:
            return {"success": False, "error": "Round not ended"}

        room.reset_for_round()
        return {"success": True, "phase": room.game_state.phase}

    def _get_data_service(self, sport: Sport) -> SportDataService:
        """Get the appropriate data service for the sport."""
        # Import here to avoid circular import
        from sports_trivia.services import get_service

        return get_service(sport)

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
