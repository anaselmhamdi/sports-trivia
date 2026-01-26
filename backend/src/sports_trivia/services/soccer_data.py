"""Soccer data service using processed JSON data."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to processed data file
DATA_FILE = Path(__file__).parent.parent / "data" / "soccer_players.json"

# Module-level cache for data
_soccer_data: dict | None = None
_soccer_data_loaded = False


def _load_soccer_data() -> dict | None:
    """Load processed soccer data from JSON file."""
    global _soccer_data, _soccer_data_loaded

    if _soccer_data_loaded:
        return _soccer_data

    _soccer_data_loaded = True

    if not DATA_FILE.exists():
        logger.info(f"Soccer data file not found: {DATA_FILE}")
        return None

    try:
        with open(DATA_FILE) as f:
            _soccer_data = json.load(f)
        logger.info(
            f"Loaded soccer data: {_soccer_data['metadata']['total_clubs']} clubs, "
            f"{_soccer_data['metadata']['total_players']} players"
        )
        return _soccer_data
    except Exception as e:
        logger.error(f"Error loading soccer data: {e}")
        return None


def _get_club_key(club_name: str) -> str | None:
    """Get the canonical club key from data."""
    data = _load_soccer_data()
    if not data:
        return None

    lower = club_name.lower().strip()

    # Check club_id_map for aliases
    if lower in data.get("club_id_map", {}):
        return data["club_id_map"][lower]

    # Check direct club names
    if lower in data.get("clubs", {}):
        return lower

    return None


class SoccerDataService:
    """Service for soccer player and club data lookups."""

    # Fallback mock data when JSON not available
    MOCK_CLUBS = {
        "barcelona": [
            "Neymar",
            "Lionel Messi",
            "Luis Suarez",
            "Thierry Henry",
            "Zlatan Ibrahimovic",
        ],
        "paris saint-germain": ["Neymar", "Lionel Messi", "Kylian Mbappe", "Zlatan Ibrahimovic"],
        "psg": ["Neymar", "Lionel Messi", "Kylian Mbappe", "Zlatan Ibrahimovic"],
        "real madrid": ["Cristiano Ronaldo", "Kylian Mbappe", "David Beckham", "Zinedine Zidane"],
        "manchester united": [
            "Cristiano Ronaldo",
            "David Beckham",
            "Zlatan Ibrahimovic",
            "Wayne Rooney",
        ],
        "juventus": ["Cristiano Ronaldo", "Zlatan Ibrahimovic", "Thierry Henry", "Zinedine Zidane"],
        "inter milan": ["Zlatan Ibrahimovic", "Ronaldo Nazario", "Samuel Eto'o"],
        "ac milan": ["Zlatan Ibrahimovic", "Ronaldo Nazario", "David Beckham", "Kaka"],
        "bayern munich": ["Robert Lewandowski", "Thomas Muller", "Franck Ribery"],
        "arsenal": ["Thierry Henry", "David Beckham", "Mesut Ozil"],
        "chelsea": ["Didier Drogba", "Eden Hazard", "Frank Lampard"],
        "liverpool": ["Luis Suarez", "Mohamed Salah", "Steven Gerrard"],
        "manchester city": ["David Silva", "Sergio Aguero", "Kevin De Bruyne"],
        "atletico madrid": ["Luis Suarez", "Antoine Griezmann", "Diego Costa"],
    }

    # Club name aliases for mock data
    CLUB_ALIASES = {
        "barca": "barcelona",
        "fc barcelona": "barcelona",
        "psg": "paris saint-germain",
        "paris sg": "paris saint-germain",
        "man united": "manchester united",
        "man utd": "manchester united",
        "mufc": "manchester united",
        "man city": "manchester city",
        "mcfc": "manchester city",
        "juve": "juventus",
        "inter": "inter milan",
        "internazionale": "inter milan",
        "milan": "ac milan",
        "bayern": "bayern munich",
        "atleti": "atletico madrid",
    }

    def __init__(self) -> None:
        # Try to load JSON data on init
        _load_soccer_data()

    def validate_club(self, club_name: str) -> bool:
        """Check if a club name is valid."""
        # Check JSON data first
        if _get_club_key(club_name):
            return True

        # Fall back to mock data
        normalized = self._normalize_club_name_mock(club_name)
        return normalized in self.MOCK_CLUBS

    def normalize_club_name(self, club_name: str) -> str:
        """Normalize club name to standard format."""
        # Check JSON data first
        data = _load_soccer_data()
        if data:
            club_key = _get_club_key(club_name)
            if club_key and club_key in data["clubs"]:
                return data["clubs"][club_key]["full_name"]

        # Fall back to mock data
        normalized = self._normalize_club_name_mock(club_name)
        if normalized in self.MOCK_CLUBS:
            name_map = {
                "barcelona": "Barcelona",
                "paris saint-germain": "Paris Saint-Germain",
                "real madrid": "Real Madrid",
                "manchester united": "Manchester United",
                "juventus": "Juventus",
                "inter milan": "Inter Milan",
                "ac milan": "AC Milan",
                "bayern munich": "Bayern Munich",
                "arsenal": "Arsenal",
                "chelsea": "Chelsea",
                "liverpool": "Liverpool",
                "manchester city": "Manchester City",
                "atletico madrid": "Atletico Madrid",
            }
            return name_map.get(normalized, normalized.title())
        return club_name.title()

    def normalize_player_name(self, player_name: str) -> str:
        """Normalize player name."""
        return player_name.strip().title()

    def find_common_players(self, club1: str, club2: str) -> list[str]:
        """Find players who played for both clubs."""
        # Try JSON data first
        data = _load_soccer_data()
        if data:
            club1_key = _get_club_key(club1)
            club2_key = _get_club_key(club2)

            if club1_key and club2_key:
                # Handle both old format (list of strings) and new format (list of dicts)
                raw_players1 = data["clubs"].get(club1_key, {}).get("players", [])
                raw_players2 = data["clubs"].get(club2_key, {}).get("players", [])

                # Extract names if players are stored as dicts
                if raw_players1 and isinstance(raw_players1[0], dict):
                    players1 = {p["name"] for p in raw_players1}
                else:
                    players1 = set(raw_players1)

                if raw_players2 and isinstance(raw_players2[0], dict):
                    players2 = {p["name"] for p in raw_players2}
                else:
                    players2 = set(raw_players2)

                common = players1 & players2
                logger.info(f"Found {len(common)} common players between {club1} and {club2}")
                return sorted(common)

        # Fall back to mock data
        club1_normalized = self._normalize_club_name_mock(club1)
        club2_normalized = self._normalize_club_name_mock(club2)

        if club1_normalized in self.MOCK_CLUBS and club2_normalized in self.MOCK_CLUBS:
            players1 = set(self.MOCK_CLUBS[club1_normalized])
            players2 = set(self.MOCK_CLUBS[club2_normalized])
            return sorted(players1 & players2)

        return []

    def get_club_players(self, club_name: str) -> list[str]:
        """Get all players who have played for a club."""
        # Try JSON data first
        data = _load_soccer_data()
        if data:
            club_key = _get_club_key(club_name)
            if club_key and club_key in data["clubs"]:
                raw_players = data["clubs"][club_key]["players"]
                # Handle both old format (list of strings) and new format (list of dicts)
                if raw_players and isinstance(raw_players[0], dict):
                    return [p["name"] for p in raw_players]
                return raw_players

        # Fall back to mock data
        normalized = self._normalize_club_name_mock(club_name)
        if normalized in self.MOCK_CLUBS:
            return self.MOCK_CLUBS[normalized]
        return []

    def get_club_info(self, club_name: str) -> dict | None:
        """Get full club info including logos.

        Returns:
            Dict with keys: id, full_name, country, badge, logo
            Or None if club not found.
        """
        data = _load_soccer_data()
        if data:
            club_key = _get_club_key(club_name)
            if club_key and club_key in data["clubs"]:
                club = data["clubs"][club_key]
                return {
                    "id": club.get("id"),
                    "full_name": club["full_name"],
                    "country": club.get("country"),
                    "badge": club.get("badge"),
                    "logo": club.get("logo"),
                }
        return None

    def get_all_clubs(self) -> list[dict]:
        """Get all clubs with their info for autocomplete/dropdown.

        Returns:
            List of club dicts with: full_name, country, badge
        """
        data = _load_soccer_data()
        if not data:
            # Return mock club names if no data
            return [
                {"full_name": name.title(), "country": None}
                for name in self.MOCK_CLUBS
                if name != "psg"  # Skip duplicate alias
            ]

        clubs = []
        for club_data in data["clubs"].values():
            clubs.append(
                {
                    "full_name": club_data["full_name"],
                    "country": club_data.get("country"),
                    "badge": club_data.get("badge"),
                }
            )

        return sorted(clubs, key=lambda c: c["full_name"])

    def _normalize_club_name_mock(self, club_name: str) -> str:
        """Normalize club name for mock data lookups."""
        lower = club_name.lower().strip()
        return self.CLUB_ALIASES.get(lower, lower)

    def get_player_details(self, player_names: list[str]) -> list[dict]:
        """Get player details including image URLs for a list of player names.

        For JSON-based data, we look up image_url from the scraped data.

        Args:
            player_names: List of player names to look up.

        Returns:
            List of dicts with: name, image_url (may be None).
        """
        data = _load_soccer_data()
        if not data:
            # No data, return names without images
            return [{"name": name, "image_url": None} for name in player_names]

        # Build lookup from data: name_lower -> {name, image_url}
        player_lookup: dict[str, dict] = {}
        for club_data in data.get("clubs", {}).values():
            for player in club_data.get("players", []):
                if isinstance(player, dict):
                    # New format with name and image_url
                    name_lower = player["name"].lower()
                    player_lookup[name_lower] = {
                        "name": player["name"],
                        "image_url": player.get("image_url"),
                    }
                else:
                    # Old format (string only) - no image_url
                    player_lookup[player.lower()] = {"name": player, "image_url": None}

        result = []
        for name in player_names:
            name_lower = name.lower()
            player_info = player_lookup.get(name_lower)
            if player_info:
                result.append(player_info)
            else:
                result.append({"name": name, "image_url": None})

        return result
