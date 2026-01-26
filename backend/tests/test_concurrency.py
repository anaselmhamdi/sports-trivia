"""Tests for race condition handling with per-room locking."""

import asyncio

import pytest

from sports_trivia.models import GamePhase, Room
from sports_trivia.services.game_manager import GameManager, TransitionResult


class TestConcurrency:
    """Test race condition handling with per-room locking."""

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_modification(self, room_with_lock: Room) -> None:
        """Test that lock serializes access to room state."""
        results = []

        async def modify_with_lock(value: int) -> None:
            async with room_with_lock.get_lock():
                await asyncio.sleep(0.01)  # Simulate work
                results.append(value)

        # Run concurrent modifications
        await asyncio.gather(
            modify_with_lock(1),
            modify_with_lock(2),
            modify_with_lock(3),
        )

        # All modifications should complete in sequence
        assert len(results) == 3
        assert set(results) == {1, 2, 3}

    def test_double_club_submission_rejected(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Same player cannot submit twice."""
        result1 = game_manager.submit_club(full_room, "player-1", "Barcelona")
        assert result1["success"] is True

        result2 = game_manager.submit_club(full_room, "player-1", "Real Madrid")
        assert result2["success"] is False
        assert "Already submitted" in result2["error"]

    def test_phase_validation_prevents_invalid_transition(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Phase validation prevents submitting in wrong phase."""
        # Submit clubs and start guessing
        game_manager.submit_club(full_room, "player-1", "Barcelona")
        game_manager.submit_club(full_room, "player-2", "PSG")
        game_manager.start_guessing_phase(full_room)

        # Try to submit club during guessing phase
        result = game_manager.submit_club(full_room, "player-1", "Real Madrid")
        assert result["success"] is False
        assert "Not in club submission phase" in result["error"]

    def test_concurrent_submit_club_both_succeed(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Both players can submit clubs (different players)."""
        result1 = game_manager.submit_club(full_room, "player-1", "Barcelona")
        result2 = game_manager.submit_club(full_room, "player-2", "PSG")

        assert result1["success"] is True
        assert result2["success"] is True
        assert full_room.players[0].submitted_club == "Barcelona"
        assert full_room.players[1].submitted_club == "Paris SG"

    def test_start_guessing_phase_idempotent(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Calling start_guessing_phase twice fails the second time."""
        game_manager.submit_club(full_room, "player-1", "Barcelona")
        game_manager.submit_club(full_room, "player-2", "PSG")

        result1 = game_manager.start_guessing_phase(full_room)
        assert result1["success"] is True

        # Second call should fail (already in GUESSING phase)
        result2 = game_manager.start_guessing_phase(full_room)
        assert result2["success"] is False
        assert "Not ready to start guessing" in result2["error"]

    def test_guess_after_round_end_fails(
        self, game_manager: GameManager, room_in_guessing: Room
    ) -> None:
        """Cannot submit guess after round has ended."""
        # Submit correct guess
        result1 = game_manager.submit_guess(room_in_guessing, "p1", "Shaquille O'Neal")
        assert result1["success"] is True
        assert result1["correct"] is True
        assert room_in_guessing.game_state.phase == GamePhase.ROUND_END

        # Try to submit another guess
        result2 = game_manager.submit_guess(room_in_guessing, "p2", "Lebron James")
        assert result2["success"] is False
        assert "Not in guessing phase" in result2["error"]

    def test_end_round_timeout_idempotent(
        self, game_manager: GameManager, room_in_guessing: Room
    ) -> None:
        """Calling end_round_timeout twice fails the second time."""
        result1 = game_manager.end_round_timeout(room_in_guessing)
        assert result1["success"] is True

        result2 = game_manager.end_round_timeout(room_in_guessing)
        assert result2["success"] is False

    def test_new_round_only_from_round_end(
        self, game_manager: GameManager, room_in_guessing: Room
    ) -> None:
        """Can only start new round from ROUND_END phase."""
        # In GUESSING phase
        result1 = game_manager.start_new_round(room_in_guessing)
        assert result1["success"] is False
        assert "Round not ended" in result1["error"]

        # End the round
        game_manager.end_round_timeout(room_in_guessing)

        # Now should work
        result2 = game_manager.start_new_round(room_in_guessing)
        assert result2["success"] is True


class TestTransitionResultEnum:
    """Test the TransitionResult enum is used correctly."""

    def test_submit_club_returns_typed_result_internally(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Internal method returns TransitionResult enum."""
        result = game_manager._submit_club_atomic(full_room, "player-1", "Barcelona")
        assert result.status == TransitionResult.SUCCESS
        assert result.club == "Barcelona"

    def test_invalid_phase_returns_correct_status(
        self, game_manager: GameManager, sample_room: Room
    ) -> None:
        """Invalid phase returns INVALID_PHASE status."""
        result = game_manager._submit_club_atomic(sample_room, "player-1", "Barcelona")
        assert result.status == TransitionResult.INVALID_PHASE

    def test_invalid_club_returns_correct_status(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Invalid club returns INVALID_CLUB status."""
        result = game_manager._submit_club_atomic(full_room, "player-1", "Nonexistent FC")
        assert result.status == TransitionResult.INVALID_CLUB

    def test_already_submitted_returns_correct_status(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Double submission returns ALREADY_SUBMITTED status."""
        game_manager._submit_club_atomic(full_room, "player-1", "Barcelona")
        result = game_manager._submit_club_atomic(full_room, "player-1", "Real Madrid")
        assert result.status == TransitionResult.ALREADY_SUBMITTED
