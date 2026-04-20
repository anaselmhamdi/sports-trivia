"""Tests for state version tracking."""

from sports_trivia.models import GamePhase, GameState, Room
from sports_trivia.services.game_manager import GameManager


class TestStateVersioning:
    """Test state version tracking and validation."""

    def test_initial_version_is_zero(self) -> None:
        """GameState starts with version 0."""
        state = GameState()
        assert state.version == 0

    def test_version_increments_on_mutation(self) -> None:
        """Version increases with each increment call."""
        state = GameState()
        initial = state.version

        state.increment_version()
        assert state.version == initial + 1

        state.increment_version()
        assert state.version == initial + 2

    def test_reset_for_round_increments_version(self) -> None:
        """Resetting for new round increments version."""
        state = GameState()
        state.phase = GamePhase.ROUND_END
        initial = state.version

        state.reset_for_round()

        assert state.version > initial
        assert state.phase == GamePhase.WAITING_FOR_CLUBS

    def test_submit_club_increments_version(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Submitting a club increments version."""
        initial = full_room.game_state.version

        game_manager.submit_club(full_room, "player-1", "Barcelona")

        assert full_room.game_state.version > initial

    def test_start_guessing_increments_version(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Starting guessing phase increments version."""
        game_manager.submit_club(full_room, "player-1", "Barcelona")
        game_manager.submit_club(full_room, "player-2", "PSG")
        initial = full_room.game_state.version

        game_manager.start_guessing_phase(full_room)

        assert full_room.game_state.version > initial

    def test_correct_guess_increments_version(
        self, game_manager: GameManager, room_in_guessing: Room
    ) -> None:
        """Correct guess increments version."""
        initial = room_in_guessing.game_state.version

        game_manager.submit_guess(room_in_guessing, "p1", "Shaquille O'Neal")

        assert room_in_guessing.game_state.version > initial

    def test_incorrect_guess_does_not_increment_version(
        self, game_manager: GameManager, room_in_guessing: Room
    ) -> None:
        """Incorrect guess does not increment version."""
        initial = room_in_guessing.game_state.version

        game_manager.submit_guess(room_in_guessing, "p1", "Michael Jordan")

        assert room_in_guessing.game_state.version == initial

    def test_timeout_increments_version(
        self, game_manager: GameManager, room_in_guessing: Room
    ) -> None:
        """Round timeout increments version."""
        initial = room_in_guessing.game_state.version

        game_manager.end_round_timeout(room_in_guessing)

        assert room_in_guessing.game_state.version > initial

    def test_version_survives_phase_transitions(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Version persists and grows across multiple phase changes."""
        versions = [full_room.game_state.version]

        # Submit clubs
        game_manager.submit_club(full_room, "player-1", "Barcelona")
        versions.append(full_room.game_state.version)

        game_manager.submit_club(full_room, "player-2", "PSG")
        versions.append(full_room.game_state.version)

        # Start guessing
        game_manager.start_guessing_phase(full_room)
        versions.append(full_room.game_state.version)

        # End round
        game_manager.end_round_timeout(full_room)
        versions.append(full_room.game_state.version)

        # New round
        game_manager.start_new_round(full_room)
        versions.append(full_room.game_state.version)

        # All versions should be strictly increasing
        for i in range(1, len(versions)):
            assert versions[i] > versions[i - 1], f"Version did not increase at step {i}"

    def test_stale_client_detection(self, game_manager: GameManager, full_room: Room) -> None:
        """Client with old version can be detected as stale."""
        client_version = full_room.game_state.version

        # Server-side state changes
        game_manager.submit_club(full_room, "player-1", "Barcelona")
        game_manager.submit_club(full_room, "player-2", "PSG")

        # Client version is now stale
        assert client_version < full_room.game_state.version
