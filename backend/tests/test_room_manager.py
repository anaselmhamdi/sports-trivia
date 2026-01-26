"""Tests for RoomManager."""

from sports_trivia.models import GamePhase, Sport
from sports_trivia.services.room_manager import RoomManager


class TestRoomManager:
    """Tests for RoomManager class."""

    def test_create_room(self, room_manager: RoomManager) -> None:
        """Test room creation."""
        room = room_manager.create_room("player-1", "Alice", Sport.NBA)

        assert room is not None
        assert len(room.code) == 4  # 4-letter room code
        assert room.sport == Sport.NBA
        assert len(room.players) == 1
        assert room.players[0].name == "Alice"
        assert room.game_state.phase == GamePhase.WAITING_FOR_PLAYERS
        assert room.code in room_manager._room_activity  # Activity tracked

    def test_join_room(self, room_manager: RoomManager) -> None:
        """Test joining an existing room."""
        room = room_manager.create_room("player-1", "Alice", Sport.SOCCER)
        room_code = room.code

        joined_room = room_manager.join_room(room_code, "player-2", "Bob")

        assert joined_room is not None
        assert len(joined_room.players) == 2
        assert joined_room.game_state.phase == GamePhase.WAITING_FOR_CLUBS

    def test_join_nonexistent_room(self, room_manager: RoomManager) -> None:
        """Test joining a room that doesn't exist."""
        result = room_manager.join_room("FAKE01", "player-1", "Alice")
        assert result is None

    def test_join_full_room(self, room_manager: RoomManager) -> None:
        """Test joining a room that is already full."""
        room = room_manager.create_room("player-1", "Alice", Sport.NBA)
        room_manager.join_room(room.code, "player-2", "Bob")

        result = room_manager.join_room(room.code, "player-3", "Charlie")
        assert result is None

    def test_leave_room(self, room_manager: RoomManager) -> None:
        """Test leaving a room."""
        room = room_manager.create_room("player-1", "Alice", Sport.NBA)
        room_manager.join_room(room.code, "player-2", "Bob")

        remaining_room, removed = room_manager.leave_room(room.code, "player-1")

        assert removed is not None
        assert removed.name == "Alice"
        assert remaining_room is not None
        assert len(remaining_room.players) == 1
        assert remaining_room.game_state.phase == GamePhase.WAITING_FOR_PLAYERS

    def test_leave_room_last_player(self, room_manager: RoomManager) -> None:
        """Test that room is deleted when last player leaves."""
        room = room_manager.create_room("player-1", "Alice", Sport.NBA)
        room_code = room.code

        result_room, removed = room_manager.leave_room(room_code, "player-1")

        assert removed is not None
        assert result_room is None
        assert not room_manager.room_exists(room_code)

    def test_get_room(self, room_manager: RoomManager) -> None:
        """Test getting a room by code."""
        room = room_manager.create_room("player-1", "Alice", Sport.NBA)

        found = room_manager.get_room(room.code)
        assert found is not None
        assert found.code == room.code

    def test_get_room_for_player(self, room_manager: RoomManager) -> None:
        """Test finding which room a player is in."""
        room = room_manager.create_room("player-1", "Alice", Sport.NBA)

        found = room_manager.get_room_for_player("player-1")
        assert found is not None
        assert found.code == room.code

        not_found = room_manager.get_room_for_player("unknown")
        assert not_found is None

    def test_room_count(self, room_manager: RoomManager) -> None:
        """Test room count tracking."""
        assert room_manager.room_count == 0

        room_manager.create_room("player-1", "Alice", Sport.NBA)
        assert room_manager.room_count == 1

        room_manager.create_room("player-2", "Bob", Sport.SOCCER)
        assert room_manager.room_count == 2
