"""Database-backed sport data service.

Provides the same interface as JSON-based services but uses SQLite for storage.
"""

import logging

from sqlalchemy.orm import Session

from sports_trivia.db import get_engine
from sports_trivia.db.repository import SportsRepository
from sports_trivia.utils.images import get_player_image_url

logger = logging.getLogger(__name__)


class DatabaseDataService:
    """Sport data service backed by SQLite database.

    Implements the SportDataService protocol using database queries
    instead of in-memory JSON data.
    """

    def __init__(self, league_slug: str):
        """Initialize service for a specific league.

        Args:
            league_slug: The league identifier (e.g., "nba", "soccer").
        """
        self.league_slug = league_slug
        self.engine = get_engine()

    def validate_club(self, name: str) -> bool:
        """Check if a club/team name is valid.

        Args:
            name: The club/team name to validate (case-insensitive).

        Returns:
            True if the club exists in the database, False otherwise.
        """
        with Session(self.engine) as session:
            repo = SportsRepository(session)
            club = repo.get_club_by_name(self.league_slug, name)
            return club is not None

    def normalize_club_name(self, name: str) -> str:
        """Normalize a club/team name to its canonical form.

        Args:
            name: The club/team name to normalize.

        Returns:
            The properly formatted canonical name (e.g., "FC Barcelona").
        """
        with Session(self.engine) as session:
            repo = SportsRepository(session)
            club = repo.get_club_by_name(self.league_slug, name)
            if club:
                return club.full_name
        return name.title()

    def normalize_player_name(self, player_name: str) -> str:
        """Normalize a player name.

        Args:
            player_name: The player name to normalize.

        Returns:
            The normalized player name.
        """
        return player_name.strip().title()

    def find_common_players(self, club1: str, club2: str) -> list[str]:
        """Find players who played for both clubs.

        Args:
            club1: First club/team name.
            club2: Second club/team name.

        Returns:
            Sorted list of player names who played for both clubs.
        """
        with Session(self.engine) as session:
            repo = SportsRepository(session)

            c1 = repo.get_club_by_name(self.league_slug, club1)
            c2 = repo.get_club_by_name(self.league_slug, club2)

            if not c1 or not c2:
                logger.warning(
                    f"Clubs not found: {club1}={c1 is not None}, {club2}={c2 is not None}"
                )
                return []

            players = repo.find_common_players(c1.id, c2.id)
            logger.info(f"Found {len(players)} common players between {club1} and {club2}")
            return [p.name for p in players]

    def get_club_players(self, name: str) -> list[str]:
        """Get all players who have played for a club.

        Args:
            name: The club/team name.

        Returns:
            List of player names.
        """
        with Session(self.engine) as session:
            repo = SportsRepository(session)
            club = repo.get_club_by_name(self.league_slug, name)

            if not club:
                return []

            players = repo.get_club_players(club.id)
            return [p.name for p in players]

    def get_club_info(self, name: str) -> dict | None:
        """Get full club/team information including logos.

        Args:
            name: The club/team name.

        Returns:
            Dict with club info or None if not found.
        """
        with Session(self.engine) as session:
            repo = SportsRepository(session)
            club = repo.get_club_by_name(self.league_slug, name)

            if not club:
                return None

            # Build response based on league type
            info = {
                "id": club.external_id,
                "full_name": club.full_name,
            }

            if self.league_slug == "nba":
                info.update(
                    {
                        "nickname": club.nickname,
                        "city": club.city,
                        "abbreviation": club.abbreviation,
                        "logo": club.logo,
                        "logo_small": club.logo_small,
                    }
                )
            else:  # soccer
                info.update(
                    {
                        "country": club.country,
                        "badge": club.badge,
                        "logo": club.logo,
                    }
                )

            return info

    def get_all_clubs(self) -> list[dict]:
        """Get all clubs/teams for autocomplete/dropdown.

        Returns:
            List of club dicts sorted by full_name.
        """
        with Session(self.engine) as session:
            repo = SportsRepository(session)
            clubs = repo.get_all_clubs(self.league_slug)

            result = []
            for club in clubs:
                if self.league_slug == "nba":
                    result.append(
                        {
                            "full_name": club.full_name,
                            "nickname": club.nickname,
                            "abbreviation": club.abbreviation,
                            "logo_small": club.logo_small,
                        }
                    )
                else:  # soccer
                    result.append(
                        {
                            "full_name": club.full_name,
                            "country": club.country,
                            "badge": club.badge,
                        }
                    )

            return result

    def get_player_details(self, player_names: list[str]) -> list[dict]:
        """Get player details including image URLs for a list of player names.

        Args:
            player_names: List of player names to look up.

        Returns:
            List of dicts with: name, image_url (may be None).
        """
        if not player_names:
            return []

        with Session(self.engine) as session:
            repo = SportsRepository(session)
            players = repo.get_players_by_names(player_names)

            # Build a lookup by normalized name
            player_lookup = {p.name_normalized: p for p in players}

            result = []
            for name in player_names:
                normalized = name.lower().strip()
                player = player_lookup.get(normalized)
                if player:
                    result.append(
                        {
                            "name": player.name,
                            "image_url": get_player_image_url(player, self.league_slug),
                        }
                    )
                else:
                    # Player not found in DB, include name without image
                    result.append({"name": name, "image_url": None})

            return result


class NBADatabaseService(DatabaseDataService):
    """NBA-specific database service."""

    def __init__(self):
        super().__init__("nba")


class SoccerDatabaseService(DatabaseDataService):
    """Soccer-specific database service."""

    def __init__(self):
        super().__init__("soccer")
