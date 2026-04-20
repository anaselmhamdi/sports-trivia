"""Tests for database-backed data services."""

import pytest

from sports_trivia.db import DATABASE_PATH

# Skip if database doesn't exist
pytestmark = pytest.mark.skipif(
    not DATABASE_PATH.exists(), reason="Database not found. Run seed_database.py first."
)


class TestNBADatabaseService:
    """Tests for NBA database service."""

    @pytest.fixture
    def nba_service(self):
        from sports_trivia.services.db_data import NBADatabaseService

        return NBADatabaseService()

    def test_validate_club_valid(self, nba_service):
        assert nba_service.validate_club("Lakers") is True
        assert nba_service.validate_club("lakers") is True
        assert nba_service.validate_club("Los Angeles Lakers") is True

    def test_validate_club_invalid(self, nba_service):
        assert nba_service.validate_club("Invalid Team") is False

    def test_normalize_club_name(self, nba_service):
        assert nba_service.normalize_club_name("lakers") == "Los Angeles Lakers"
        assert nba_service.normalize_club_name("Lakers") == "Los Angeles Lakers"

    def test_find_common_players(self, nba_service):
        common = nba_service.find_common_players("Lakers", "Heat")
        assert len(common) > 0
        # Both Shaq and LeBron played for both teams
        common_lower = [p.lower() for p in common]
        assert any("shaquille" in p or "o'neal" in p for p in common_lower)

    def test_get_club_players(self, nba_service):
        players = nba_service.get_club_players("Lakers")
        assert len(players) > 10
        assert isinstance(players, list)
        assert all(isinstance(p, str) for p in players)

    def test_get_club_info(self, nba_service):
        info = nba_service.get_club_info("Lakers")
        assert info is not None
        assert info["full_name"] == "Los Angeles Lakers"
        assert info["nickname"] == "Lakers"
        assert info["abbreviation"] == "LAL"

    def test_get_all_clubs(self, nba_service):
        clubs = nba_service.get_all_clubs()
        assert len(clubs) == 30  # 30 NBA teams
        assert all("full_name" in c for c in clubs)


class TestSoccerDatabaseService:
    """Tests for Soccer database service."""

    @pytest.fixture
    def soccer_service(self):
        from sports_trivia.services.db_data import SoccerDatabaseService

        return SoccerDatabaseService()

    def test_validate_club_valid(self, soccer_service):
        assert soccer_service.validate_club("Juventus") is True
        assert soccer_service.validate_club("juventus") is True
        assert soccer_service.validate_club("Inter") is True

    def test_validate_club_invalid(self, soccer_service):
        assert soccer_service.validate_club("Invalid Club") is False

    def test_normalize_club_name(self, soccer_service):
        assert soccer_service.normalize_club_name("juventus") == "Juventus"
        assert soccer_service.normalize_club_name("inter") == "Inter"

    def test_find_common_players(self, soccer_service):
        common = soccer_service.find_common_players("Juventus", "AC Milan")
        assert len(common) > 0
        # Pirlo played for both
        common_lower = [p.lower() for p in common]
        assert any("pirlo" in p for p in common_lower)

    def test_get_club_players(self, soccer_service):
        players = soccer_service.get_club_players("Juventus")
        assert len(players) > 10
        assert isinstance(players, list)

    def test_get_club_info(self, soccer_service):
        info = soccer_service.get_club_info("Juventus")
        assert info is not None
        assert info["full_name"] == "Juventus"

    def test_get_all_clubs(self, soccer_service):
        clubs = soccer_service.get_all_clubs()
        assert len(clubs) == 500
        assert all("full_name" in c for c in clubs)
