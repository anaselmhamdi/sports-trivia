"""Base protocol for sport-specific data services."""

from typing import Protocol


class SportDataService(Protocol):
    """Protocol for sport-specific data services.

    All sport data services (NBA, Soccer, etc.) must implement this interface
    to ensure consistent behavior across the application.
    """

    def validate_club(self, name: str) -> bool:
        """Check if a club/team name is valid.

        Args:
            name: The club/team name to validate (case-insensitive).

        Returns:
            True if the club exists in the data source, False otherwise.
        """
        ...

    def normalize_club_name(self, name: str) -> str:
        """Normalize a club/team name to its canonical form.

        Args:
            name: The club/team name to normalize.

        Returns:
            The properly formatted canonical name (e.g., "FC Barcelona").
        """
        ...

    def normalize_player_name(self, name: str) -> str:
        """Normalize a player name.

        Args:
            name: The player name to normalize.

        Returns:
            The normalized player name.
        """
        ...

    def find_common_players(self, club1: str, club2: str) -> list[str]:
        """Find players who played for both clubs.

        Args:
            club1: First club/team name.
            club2: Second club/team name.

        Returns:
            Sorted list of player names who played for both clubs.
        """
        ...

    def get_club_players(self, name: str) -> list[str]:
        """Get all players who have played for a club.

        Args:
            name: The club/team name.

        Returns:
            List of player names.
        """
        ...

    def get_club_info(self, name: str) -> dict | None:
        """Get full club/team information including logos.

        Args:
            name: The club/team name.

        Returns:
            Dict with keys like: id, full_name, logo, logo_small, country, etc.
            Returns None if club not found.
        """
        ...

    def get_all_clubs(self) -> list[dict]:
        """Get all clubs/teams for autocomplete/dropdown.

        Returns:
            List of club dicts with: full_name, nickname/short_name, logo_small, etc.
        """
        ...

    def get_player_details(self, player_names: list[str]) -> list[dict]:
        """Get player details including image URLs for a list of player names.

        Args:
            player_names: List of player names to look up.

        Returns:
            List of dicts with: name, image_url (may be None).
        """
        ...
