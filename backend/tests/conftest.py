"""Pytest fixtures for Sports Trivia tests."""

import pytest

from sports_trivia.models import GamePhase, GameState, Player, Room, Sport
from sports_trivia.services.game_manager import GameManager
from sports_trivia.services.room_manager import RoomManager


@pytest.fixture
def room_manager() -> RoomManager:
    """Create a fresh RoomManager instance."""
    return RoomManager()


@pytest.fixture
def game_manager() -> GameManager:
    """Create a fresh GameManager instance."""
    return GameManager()


@pytest.fixture
def sample_player() -> Player:
    """Create a sample player."""
    return Player(id="player-1", name="Test Player")


@pytest.fixture
def sample_room() -> Room:
    """Create a sample room with one player."""
    room = Room(code="TEST01", sport=Sport.NBA, game_state=GameState())
    room.add_player(Player(id="player-1", name="Player 1"))
    return room


@pytest.fixture
def full_room() -> Room:
    """Create a room with two players ready for club submission."""
    room = Room(code="FULL01", sport=Sport.SOCCER, game_state=GameState())
    room.add_player(Player(id="player-1", name="Player 1"))
    room.add_player(Player(id="player-2", name="Player 2"))
    return room


@pytest.fixture
def room_with_lock() -> Room:
    """Room with initialized lock for concurrency tests."""
    room = Room(code="LOCK01", sport=Sport.NBA, game_state=GameState())
    room.add_player(Player(id="p1", name="Alice"))
    room.add_player(Player(id="p2", name="Bob"))
    room.game_state.phase = GamePhase.WAITING_FOR_CLUBS
    # Initialize lock
    _ = room.get_lock()
    return room


@pytest.fixture
def room_in_guessing(room_with_lock: Room, game_manager: GameManager) -> Room:
    """Room already in guessing phase."""
    room = room_with_lock
    room.players[0].submitted_club = "Los Angeles Lakers"
    room.players[1].submitted_club = "Miami Heat"
    game_manager.start_guessing_phase(room)
    return room
