"""Tests for multiplayer game mode."""

import pytest

from sports_trivia.models import (
    GameMode,
    GamePhase,
    GameState,
    Player,
    Room,
    Sport,
)
from sports_trivia.services.game_manager import GameManager
from sports_trivia.services.room_manager import RoomManager


@pytest.fixture
def multiplayer_room() -> Room:
    """Create a multiplayer room with the host player."""
    room = Room(
        code="MULTI1",
        sport=Sport.SOCCER,
        mode=GameMode.MULTIPLAYER,
        max_players=6,
        host_id="host-1",
        game_state=GameState(),
    )
    room.add_player(Player(id="host-1", name="Host"))
    return room


@pytest.fixture
def multiplayer_room_with_players() -> Room:
    """Create a multiplayer room with 4 players."""
    room = Room(
        code="MULTI2",
        sport=Sport.SOCCER,
        mode=GameMode.MULTIPLAYER,
        max_players=6,
        host_id="host-1",
        game_state=GameState(),
    )
    room.add_player(Player(id="host-1", name="Host"))
    room.add_player(Player(id="player-2", name="Player 2"))
    room.add_player(Player(id="player-3", name="Player 3"))
    room.add_player(Player(id="player-4", name="Player 4"))
    return room


class TestMultiplayerRoomCreation:
    """Tests for multiplayer room creation."""

    def test_create_multiplayer_room(self, room_manager: RoomManager) -> None:
        """Test creating a multiplayer room."""
        room = room_manager.create_room(
            player_id="host-1",
            player_name="Host",
            sport=Sport.SOCCER,
            mode=GameMode.MULTIPLAYER,
            max_players=6,
        )

        assert room.mode == GameMode.MULTIPLAYER
        assert room.max_players == 6
        assert room.host_id == "host-1"
        # Multiplayer rooms stay in WAITING_FOR_PLAYERS until host starts
        assert room.game_state.phase == GamePhase.WAITING_FOR_PLAYERS

    def test_max_players_enforced(self, room_manager: RoomManager) -> None:
        """Test that max_players is clamped to 2-10."""
        # Too low
        room_low = room_manager.create_room(
            player_id="host-1",
            player_name="Host",
            sport=Sport.SOCCER,
            mode=GameMode.MULTIPLAYER,
            max_players=1,
        )
        assert room_low.max_players == 2

        # Too high
        room_high = room_manager.create_room(
            player_id="host-2",
            player_name="Host",
            sport=Sport.SOCCER,
            mode=GameMode.MULTIPLAYER,
            max_players=20,
        )
        assert room_high.max_players == 10

    def test_classic_mode_forces_two_players(self, room_manager: RoomManager) -> None:
        """Test that classic mode always has max_players=2."""
        room = room_manager.create_room(
            player_id="host-1",
            player_name="Host",
            sport=Sport.SOCCER,
            mode=GameMode.CLASSIC,
            max_players=6,  # Should be ignored
        )
        assert room.max_players == 2

    def test_multiplayer_room_can_have_more_than_two_players(self, multiplayer_room: Room) -> None:
        """Test that multiplayer rooms can have more than 2 players."""
        assert multiplayer_room.add_player(Player(id="player-2", name="Player 2"))
        assert multiplayer_room.add_player(Player(id="player-3", name="Player 3"))
        assert multiplayer_room.add_player(Player(id="player-4", name="Player 4"))

        assert len(multiplayer_room.players) == 4
        assert not multiplayer_room.is_full()

    def test_multiplayer_room_respects_max_players(self, multiplayer_room: Room) -> None:
        """Test that multiplayer rooms respect max_players limit."""
        # Add 5 more players (host + 5 = 6, which is max)
        for i in range(2, 7):
            assert multiplayer_room.add_player(Player(id=f"player-{i}", name=f"Player {i}"))

        assert multiplayer_room.is_full()
        assert not multiplayer_room.add_player(Player(id="player-7", name="Player 7"))


class TestStartGame:
    """Tests for start_game (WAITING_FOR_PLAYERS → WAITING_FOR_CLUBS)."""

    def test_host_can_start_game(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that host can start the game."""
        result = game_manager.start_game(multiplayer_room_with_players, "host-1")

        assert result["success"] is True
        assert multiplayer_room_with_players.game_state.phase == GamePhase.WAITING_FOR_CLUBS

    def test_non_host_cannot_start_game(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that non-host cannot start the game."""
        result = game_manager.start_game(multiplayer_room_with_players, "player-2")

        assert result["success"] is False
        assert "Only host" in result["error"]

    def test_cannot_start_with_one_player(
        self, game_manager: GameManager, multiplayer_room: Room
    ) -> None:
        """Test that game cannot start with less than 2 players."""
        result = game_manager.start_game(multiplayer_room, "host-1")

        assert result["success"] is False
        assert "at least 2 players" in result["error"]

    def test_start_game_invalid_for_classic_mode(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Test that start_game is invalid for classic mode."""
        result = game_manager.start_game(full_room, "player-1")

        assert result["success"] is False
        assert "multiplayer" in result["error"].lower()


class TestClubPool:
    """Tests for club pool submission in multiplayer mode."""

    def test_submit_club_to_pool(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test submitting a club to the pool."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        result = game_manager.submit_club(room, "host-1", "Barcelona")

        assert result["success"] is True
        assert result["club"] == "Barcelona"
        assert result["pool_size"] == 1
        assert len(room.game_state.club_pool) == 1
        assert room.game_state.club_pool[0].player_id == "host-1"
        assert room.game_state.club_pool[0].club_name == "Barcelona"

    def test_submit_duplicate_club_rejected(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that duplicate clubs are rejected."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        game_manager.submit_club(room, "host-1", "Barcelona")
        result = game_manager.submit_club(room, "player-2", "Barcelona")

        assert result["success"] is False
        assert "already in pool" in result["error"]

    def test_player_can_only_submit_once(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that a player can only submit one club."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        game_manager.submit_club(room, "host-1", "Barcelona")
        result = game_manager.submit_club(room, "host-1", "Real Madrid")

        assert result["success"] is False
        assert "Already submitted" in result["error"]

    def test_multiple_players_submit_to_pool(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test multiple players submitting to the pool."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")
        game_manager.submit_club(room, "player-3", "Real Madrid")
        result = game_manager.submit_club(room, "player-4", "Manchester United")

        assert result["success"] is True
        assert result["pool_size"] == 4
        assert len(room.game_state.club_pool) == 4


class TestStartRound:
    """Tests for start_round (select clubs and begin guessing)."""

    def test_start_round_success(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test starting a round with valid clubs."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        # Submit clubs with known common players
        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")

        result = game_manager.start_round(room, "host-1", clubs_per_round=2)

        assert result["success"] is True
        assert len(result["clubs"]) == 2
        assert result["valid_count"] > 0
        assert room.game_state.phase == GamePhase.GUESSING

    def test_non_host_cannot_start_round(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that non-host cannot start the round."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")
        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")

        result = game_manager.start_round(room, "player-2")

        assert result["success"] is False
        assert "Only host" in result["error"]

    def test_start_round_insufficient_clubs(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that round cannot start with less than 2 clubs."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")
        game_manager.submit_club(room, "host-1", "Barcelona")

        result = game_manager.start_round(room, "host-1")

        assert result["success"] is False
        assert "at least 2 clubs" in result["error"]

    def test_clubs_per_round_capped_by_pool_size(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that clubs_per_round is capped by pool size."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        # Only 2 clubs in pool
        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")

        # Request 4 clubs, should only select 2
        result = game_manager.start_round(room, "host-1", clubs_per_round=4)

        assert result["success"] is True
        assert len(result["clubs"]) == 2


class TestMultiClubSelection:
    """Tests for selecting 3-4 clubs."""

    def test_select_3_clubs(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test selecting 3 clubs from pool."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        # Submit clubs that likely share a player (Zlatan played for many)
        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")
        game_manager.submit_club(room, "player-3", "Manchester United")

        result = game_manager.start_round(room, "host-1", clubs_per_round=3)

        # May fallback to 2 if no common player for all 3
        assert result["success"] is True
        assert len(result["clubs"]) >= 2


class TestPlayAgainMultiplayer:
    """Tests for play again in multiplayer mode."""

    def test_play_again_instant_repick(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that play again in multiplayer instantly re-picks from pool."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        # Submit clubs
        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")
        game_manager.submit_club(room, "player-3", "Manchester United")
        game_manager.submit_club(room, "player-4", "Juventus")

        # Start first round
        game_manager.start_round(room, "host-1", clubs_per_round=2)

        # End round by submitting correct guess
        game_manager.submit_guess(room, "host-1", "Zlatan Ibrahimovic")
        assert room.game_state.phase == GamePhase.ROUND_END

        # Play again - should immediately start new round
        original_pool_size = len(room.game_state.club_pool)
        result = game_manager.start_new_round(room, "host-1")

        assert result["success"] is True
        assert len(result.get("clubs", [])) >= 2
        assert room.game_state.phase == GamePhase.GUESSING
        # Pool should be preserved
        assert len(room.game_state.club_pool) == original_pool_size

    def test_play_again_non_host_rejected(
        self, game_manager: GameManager, multiplayer_room_with_players: Room
    ) -> None:
        """Test that non-host cannot trigger play again in multiplayer."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")
        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")
        game_manager.start_round(room, "host-1", clubs_per_round=2)
        game_manager.submit_guess(room, "host-1", "Neymar")

        result = game_manager.start_new_round(room, "player-2")

        assert result["success"] is False
        assert "host" in result["error"].lower()


class TestPlayerLeaving:
    """Tests for player leaving multiplayer room."""

    def test_player_leave_removes_from_pool(
        self, multiplayer_room_with_players: Room, game_manager: GameManager
    ) -> None:
        """Test that leaving player's club is removed from pool."""
        room = multiplayer_room_with_players
        game_manager.start_game(room, "host-1")

        game_manager.submit_club(room, "host-1", "Barcelona")
        game_manager.submit_club(room, "player-2", "PSG")

        assert len(room.game_state.club_pool) == 2

        # Player 2 leaves
        room.remove_player("player-2")

        assert len(room.game_state.club_pool) == 1
        assert room.game_state.club_pool[0].player_id == "host-1"

    def test_host_transfer_on_leave(self, multiplayer_room_with_players: Room) -> None:
        """Test that host is transferred when host leaves."""
        room = multiplayer_room_with_players
        original_host = room.host_id

        room.remove_player(original_host)

        # Host should be transferred to next player
        assert room.host_id != original_host
        assert room.host_id == "player-2"


class TestClassicModeUnchanged:
    """Tests to ensure classic mode remains unchanged."""

    def test_classic_mode_auto_transition(self, room_manager: RoomManager) -> None:
        """Test that classic mode auto-transitions to WAITING_FOR_CLUBS."""
        room = room_manager.create_room(
            player_id="player-1",
            player_name="Player 1",
            sport=Sport.SOCCER,
            mode=GameMode.CLASSIC,
        )

        assert room.game_state.phase == GamePhase.WAITING_FOR_PLAYERS

        room_manager.join_room(room.code, "player-2", "Player 2")

        # Should auto-transition in classic mode
        room = room_manager.get_room(room.code)
        assert room.game_state.phase == GamePhase.WAITING_FOR_CLUBS

    def test_classic_mode_no_pool(self, game_manager: GameManager, full_room: Room) -> None:
        """Test that classic mode doesn't use pool."""
        result = game_manager.submit_club(full_room, "player-1", "Barcelona")

        assert result["success"] is True
        assert full_room.players[0].submitted_club == "Barcelona"
        assert len(full_room.game_state.club_pool) == 0

    def test_classic_play_again_resets_clubs(
        self, game_manager: GameManager, full_room: Room
    ) -> None:
        """Test that classic mode play again resets club submissions."""
        game_manager.submit_club(full_room, "player-1", "Barcelona")
        game_manager.submit_club(full_room, "player-2", "PSG")
        game_manager.start_guessing_phase(full_room)
        game_manager.submit_guess(full_room, "player-1", "Neymar")

        result = game_manager.start_new_round(full_room)

        assert result["success"] is True
        assert full_room.game_state.phase == GamePhase.WAITING_FOR_CLUBS
        assert full_room.players[0].submitted_club is None
        assert full_room.players[1].submitted_club is None
