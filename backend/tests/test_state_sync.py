"""Tests for STATE_SYNC event handling."""

import pytest
from fastapi.testclient import TestClient

from sports_trivia.main import app


class TestStateSyncEvent:
    """Test STATE_SYNC event handling."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_sync_state_not_in_room(self, client: TestClient) -> None:
        """sync_state fails when not in a room."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"event": "sync_state", "data": {}})
            response = ws.receive_json()

            assert response["event"] == "error"
            assert "not in a room" in response["data"]["message"].lower()

    def test_sync_state_in_lobby(self, client: TestClient) -> None:
        """sync_state returns state when in lobby (waiting for opponent)."""
        with client.websocket_connect("/ws") as ws:
            # Create room
            ws.send_json({"event": "create_room", "data": {"player_name": "Alice", "sport": "nba"}})
            create_response = ws.receive_json()
            room_code = create_response["data"]["room_code"]

            # Request state sync
            ws.send_json({"event": "sync_state", "data": {}})
            sync_response = ws.receive_json()

            assert sync_response["event"] == "state_sync"
            data = sync_response["data"]
            assert data["room_code"] == room_code
            assert data["sport"] == "nba"
            assert data["phase"] == "waiting_for_players"
            assert "version" in data
            assert data["self_player"]["name"] == "Alice"
            assert data["opponent"] is None

    def test_sync_state_with_opponent(self, client: TestClient) -> None:
        """sync_state includes opponent info when present."""
        with client.websocket_connect("/ws") as ws1:
            # Create room
            ws1.send_json(
                {"event": "create_room", "data": {"player_name": "Alice", "sport": "nba"}}
            )
            create_response = ws1.receive_json()
            room_code = create_response["data"]["room_code"]

            with client.websocket_connect("/ws") as ws2:
                # Join room
                ws2.send_json(
                    {
                        "event": "join_room",
                        "data": {"room_code": room_code, "player_name": "Bob"},
                    }
                )
                ws2.receive_json()  # room_joined
                ws1.receive_json()  # player_joined

                # Request state sync from player 1
                ws1.send_json({"event": "sync_state", "data": {}})
                sync_response = ws1.receive_json()

                assert sync_response["event"] == "state_sync"
                data = sync_response["data"]
                assert data["phase"] == "waiting_for_clubs"
                assert data["self_player"]["name"] == "Alice"
                assert data["opponent"]["name"] == "Bob"

    def test_sync_state_during_guessing(self, client: TestClient) -> None:
        """sync_state returns clubs during guessing phase."""
        with client.websocket_connect("/ws") as ws1:
            # Create room
            ws1.send_json(
                {"event": "create_room", "data": {"player_name": "Alice", "sport": "soccer"}}
            )
            create_response = ws1.receive_json()
            room_code = create_response["data"]["room_code"]

            with client.websocket_connect("/ws") as ws2:
                # Join room
                ws2.send_json(
                    {
                        "event": "join_room",
                        "data": {"room_code": room_code, "player_name": "Bob"},
                    }
                )
                ws2.receive_json()  # room_joined
                ws1.receive_json()  # player_joined

                # Submit clubs
                ws1.send_json({"event": "submit_club", "data": {"club_name": "Barcelona"}})
                ws2.send_json({"event": "submit_club", "data": {"club_name": "PSG"}})

                # Drain messages until guessing_started
                for _ in range(5):
                    msg = ws1.receive_json()
                    if msg["event"] == "guessing_started":
                        break

                # Request state sync
                ws1.send_json({"event": "sync_state", "data": {}})
                sync_response = ws1.receive_json()

                assert sync_response["event"] == "state_sync"
                data = sync_response["data"]
                assert data["phase"] == "guessing"
                assert data["my_club"] is not None
                assert data["opponent_club"] is not None
                assert data["valid_answer_count"] > 0
                assert data["deadline"] is not None

    def test_sync_state_club_assignment_correct(self, client: TestClient) -> None:
        """sync_state assigns clubs correctly per player."""
        with client.websocket_connect("/ws") as ws1:
            # Create room (player 1)
            ws1.send_json(
                {"event": "create_room", "data": {"player_name": "Alice", "sport": "soccer"}}
            )
            create_response = ws1.receive_json()
            room_code = create_response["data"]["room_code"]

            with client.websocket_connect("/ws") as ws2:
                # Join room (player 2)
                ws2.send_json(
                    {
                        "event": "join_room",
                        "data": {"room_code": room_code, "player_name": "Bob"},
                    }
                )
                ws2.receive_json()  # room_joined
                ws1.receive_json()  # player_joined

                # Player 1 submits Barcelona, Player 2 submits PSG
                ws1.send_json({"event": "submit_club", "data": {"club_name": "Barcelona"}})
                ws2.send_json({"event": "submit_club", "data": {"club_name": "PSG"}})

                # Drain until guessing phase
                for _ in range(5):
                    msg = ws1.receive_json()
                    if msg["event"] == "guessing_started":
                        break
                for _ in range(5):
                    msg = ws2.receive_json()
                    if msg["event"] == "guessing_started":
                        break

                # Request state sync from both players
                ws1.send_json({"event": "sync_state", "data": {}})
                ws2.send_json({"event": "sync_state", "data": {}})

                sync1 = ws1.receive_json()
                sync2 = ws2.receive_json()

                # Each player should see their club as "my_club"
                assert sync1["data"]["my_club"] == "Barcelona"
                assert sync1["data"]["opponent_club"] == "Paris SG"

                assert sync2["data"]["my_club"] == "Paris SG"
                assert sync2["data"]["opponent_club"] == "Barcelona"

    def test_sync_state_includes_version(self, client: TestClient) -> None:
        """sync_state includes state version for stale detection."""
        with client.websocket_connect("/ws") as ws:
            # Create room
            ws.send_json({"event": "create_room", "data": {"player_name": "Alice", "sport": "nba"}})
            ws.receive_json()  # room_created

            # Request state sync
            ws.send_json({"event": "sync_state", "data": {}})
            sync_response = ws.receive_json()

            assert "version" in sync_response["data"]
            assert isinstance(sync_response["data"]["version"], int)

    def test_sync_state_submission_status(self, client: TestClient) -> None:
        """sync_state includes club submission status."""
        with client.websocket_connect("/ws") as ws1:
            # Create room
            ws1.send_json(
                {"event": "create_room", "data": {"player_name": "Alice", "sport": "soccer"}}
            )
            create_response = ws1.receive_json()
            room_code = create_response["data"]["room_code"]

            with client.websocket_connect("/ws") as ws2:
                # Join room
                ws2.send_json(
                    {
                        "event": "join_room",
                        "data": {"room_code": room_code, "player_name": "Bob"},
                    }
                )
                ws2.receive_json()  # room_joined
                ws1.receive_json()  # player_joined

                # Only player 1 submits
                ws1.send_json({"event": "submit_club", "data": {"club_name": "Barcelona"}})
                ws1.receive_json()  # club_submitted
                ws2.receive_json()  # club_submitted

                # Request state sync
                ws1.send_json({"event": "sync_state", "data": {}})
                sync_response = ws1.receive_json()

                data = sync_response["data"]
                assert data["self_player"]["submitted"] is True
                assert data["opponent"]["submitted"] is False
