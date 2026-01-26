"""WebSocket integration tests."""

import pytest
from fastapi.testclient import TestClient

from sports_trivia.main import app


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "rooms" in data

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Clutch"
        assert data["websocket"] == "/ws"

    def test_websocket_create_room(self, client: TestClient) -> None:
        """Test creating a room via WebSocket."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"event": "create_room", "data": {"player_name": "Alice", "sport": "nba"}})
            response = ws.receive_json()

            assert response["event"] == "room_created"
            assert "room_code" in response["data"]
            assert response["data"]["sport"] == "nba"
            assert response["data"]["player"]["name"] == "Alice"

    def test_websocket_join_room(self, client: TestClient) -> None:
        """Test joining a room via WebSocket."""
        # First, create a room
        with client.websocket_connect("/ws") as ws1:
            ws1.send_json(
                {"event": "create_room", "data": {"player_name": "Alice", "sport": "nba"}}
            )
            create_response = ws1.receive_json()
            room_code = create_response["data"]["room_code"]

            # Join with second player
            with client.websocket_connect("/ws") as ws2:
                ws2.send_json(
                    {"event": "join_room", "data": {"room_code": room_code, "player_name": "Bob"}}
                )
                join_response = ws2.receive_json()

                assert join_response["event"] == "room_joined"
                assert join_response["data"]["room_code"] == room_code
                assert len(join_response["data"]["players"]) == 2
                assert join_response["data"]["phase"] == "waiting_for_clubs"

                # First player should receive notification
                notification = ws1.receive_json()
                assert notification["event"] == "player_joined"
                assert notification["data"]["player"]["name"] == "Bob"

    def test_websocket_join_invalid_room(self, client: TestClient) -> None:
        """Test joining a non-existent room."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"event": "join_room", "data": {"room_code": "FAKE01", "player_name": "Alice"}}
            )
            response = ws.receive_json()

            assert response["event"] == "error"
            assert "not found" in response["data"]["message"].lower()

    def test_websocket_submit_club(self, client: TestClient) -> None:
        """Test submitting clubs."""
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
                    {"event": "join_room", "data": {"room_code": room_code, "player_name": "Bob"}}
                )
                ws2.receive_json()  # room_joined
                ws1.receive_json()  # player_joined

                # Submit clubs
                ws1.send_json({"event": "submit_club", "data": {"club_name": "Barcelona"}})
                ws1.receive_json()  # club_submitted notification

                ws2.send_json({"event": "submit_club", "data": {"club_name": "PSG"}})

                # Both should receive guessing_started
                response1 = ws1.receive_json()
                # Could be club_submitted or guessing_started depending on timing
                while response1["event"] == "club_submitted":
                    response1 = ws1.receive_json()

                assert response1["event"] == "guessing_started"
                assert response1["data"]["valid_count"] > 0

    def test_websocket_full_game_flow(self, client: TestClient) -> None:
        """Test a complete game flow."""
        with client.websocket_connect("/ws") as ws1:
            # Create room
            ws1.send_json(
                {"event": "create_room", "data": {"player_name": "Alice", "sport": "soccer"}}
            )
            create_response = ws1.receive_json()
            room_code = create_response["data"]["room_code"]

            with client.websocket_connect("/ws") as ws2:
                # Join
                ws2.send_json(
                    {"event": "join_room", "data": {"room_code": room_code, "player_name": "Bob"}}
                )
                ws2.receive_json()  # room_joined
                ws1.receive_json()  # player_joined

                # Submit clubs
                ws1.send_json({"event": "submit_club", "data": {"club_name": "Barcelona"}})
                ws2.send_json({"event": "submit_club", "data": {"club_name": "PSG"}})

                # Drain club_submitted and get to guessing_started
                for _ in range(5):
                    msg = ws1.receive_json()
                    if msg["event"] == "guessing_started":
                        break

                # Submit correct guess
                ws1.send_json({"event": "submit_guess", "data": {"player_name": "Neymar"}})

                # Should get guess_result and round_ended
                messages = []
                for _ in range(3):
                    try:
                        msg = ws1.receive_json()
                        messages.append(msg)
                        if msg["event"] == "round_ended":
                            break
                    except Exception:
                        break

                events = [m["event"] for m in messages]
                assert "round_ended" in events

                round_end = next(m for m in messages if m["event"] == "round_ended")
                assert round_end["data"]["winner_id"] is not None
                assert "Neymar" in round_end["data"]["valid_answers"]
