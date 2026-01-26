"""Tests for room TTL and cleanup logic."""

from datetime import datetime, timedelta

import pytest

from sports_trivia.models import Sport
from sports_trivia.services.room_manager import RoomManager


class TestRoomActivityTracking:
    """Test room activity tracking."""

    def test_create_room_sets_activity(self, room_manager: RoomManager) -> None:
        """Creating a room sets initial activity timestamp."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)

        assert room.code in room_manager._room_activity
        assert room_manager._room_activity[room.code] <= datetime.now()

    def test_join_room_updates_activity(self, room_manager: RoomManager) -> None:
        """Joining a room updates activity timestamp."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)
        old_activity = room_manager._room_activity[room.code]

        # Small delay to ensure different timestamp
        import time

        time.sleep(0.01)

        room_manager.join_room(room.code, "p2", "Bob")

        assert room_manager._room_activity[room.code] >= old_activity

    def test_leave_room_updates_activity(self, room_manager: RoomManager) -> None:
        """Leaving a room (with remaining players) updates activity."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)
        room_manager.join_room(room.code, "p2", "Bob")
        old_activity = room_manager._room_activity[room.code]

        import time

        time.sleep(0.01)

        room_manager.leave_room(room.code, "p1")

        assert room_manager._room_activity[room.code] >= old_activity

    def test_leave_room_last_player_removes_activity(self, room_manager: RoomManager) -> None:
        """When last player leaves, activity tracking is cleaned up."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)
        code = room.code

        room_manager.leave_room(code, "p1")

        assert code not in room_manager._room_activity

    def test_touch_room_updates_activity(self, room_manager: RoomManager) -> None:
        """touch_room explicitly updates activity timestamp."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)
        old_activity = room_manager._room_activity[room.code]

        import time

        time.sleep(0.01)

        room_manager.touch_room(room.code)

        assert room_manager._room_activity[room.code] > old_activity

    def test_get_room_last_activity(self, room_manager: RoomManager) -> None:
        """get_room_last_activity returns correct timestamp."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)

        activity = room_manager.get_room_last_activity(room.code)

        assert activity is not None
        assert activity <= datetime.now()

    def test_get_room_last_activity_nonexistent(self, room_manager: RoomManager) -> None:
        """get_room_last_activity returns None for nonexistent room."""
        activity = room_manager.get_room_last_activity("FAKE01")
        assert activity is None


class TestRoomCleanup:
    """Test room cleanup logic."""

    @pytest.mark.asyncio
    async def test_cleanup_inactive_rooms(self, room_manager: RoomManager) -> None:
        """Rooms inactive beyond TTL are removed."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)
        code = room.code

        # Backdate activity beyond TTL
        room_manager._room_activity[code] = datetime.now() - timedelta(
            minutes=room_manager.ROOM_TTL_MINUTES + 1
        )

        await room_manager._cleanup_inactive_rooms()

        assert room_manager.get_room(code) is None
        assert code not in room_manager._room_activity

    @pytest.mark.asyncio
    async def test_active_room_not_cleaned(self, room_manager: RoomManager) -> None:
        """Recently active rooms are preserved."""
        room = room_manager.create_room("p1", "Alice", Sport.NBA)
        room_manager.touch_room(room.code)

        await room_manager._cleanup_inactive_rooms()

        assert room_manager.get_room(room.code) is not None

    @pytest.mark.asyncio
    async def test_cleanup_multiple_rooms(self, room_manager: RoomManager) -> None:
        """Cleanup handles multiple rooms correctly."""
        # Create 3 rooms
        room1 = room_manager.create_room("p1", "Alice", Sport.NBA)
        room2 = room_manager.create_room("p2", "Bob", Sport.SOCCER)
        room3 = room_manager.create_room("p3", "Charlie", Sport.NBA)

        # Make room1 and room3 expired
        expired_time = datetime.now() - timedelta(minutes=room_manager.ROOM_TTL_MINUTES + 1)
        room_manager._room_activity[room1.code] = expired_time
        room_manager._room_activity[room3.code] = expired_time

        # room2 stays active
        room_manager.touch_room(room2.code)

        await room_manager._cleanup_inactive_rooms()

        # Only room2 should remain
        assert room_manager.get_room(room1.code) is None
        assert room_manager.get_room(room2.code) is not None
        assert room_manager.get_room(room3.code) is None
        assert room_manager.room_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_empty_rooms_dict(self, room_manager: RoomManager) -> None:
        """Cleanup handles empty rooms gracefully."""
        await room_manager._cleanup_inactive_rooms()
        assert room_manager.room_count == 0


class TestCleanupTask:
    """Test background cleanup task."""

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self, room_manager: RoomManager) -> None:
        """Cleanup task can be started."""
        await room_manager.start_cleanup_task()

        assert room_manager._cleanup_task is not None
        assert not room_manager._cleanup_task.done()

        await room_manager.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(self, room_manager: RoomManager) -> None:
        """Cleanup task can be stopped."""
        await room_manager.start_cleanup_task()
        await room_manager.stop_cleanup_task()

        assert room_manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_start_cleanup_task_idempotent(self, room_manager: RoomManager) -> None:
        """Starting cleanup task twice doesn't create multiple tasks."""
        await room_manager.start_cleanup_task()
        task1 = room_manager._cleanup_task

        await room_manager.start_cleanup_task()
        task2 = room_manager._cleanup_task

        assert task1 is task2

        await room_manager.stop_cleanup_task()
