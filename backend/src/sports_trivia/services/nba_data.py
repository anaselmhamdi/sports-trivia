"""NBA data service using nba_api."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from sports_trivia.config import settings

logger = logging.getLogger(__name__)

# Path to scraped data file
DATA_FILE = Path(__file__).parent.parent / "data" / "nba_players.json"

# Module-level cache for scraped data
_scraped_data: dict | None = None
_scraped_data_loaded = False


def _load_scraped_data() -> dict | None:
    """Load scraped NBA data from JSON file."""
    global _scraped_data, _scraped_data_loaded

    if _scraped_data_loaded:
        return _scraped_data

    _scraped_data_loaded = True

    if not DATA_FILE.exists():
        logger.info(f"Scraped data file not found: {DATA_FILE}")
        return None

    try:
        with open(DATA_FILE) as f:
            _scraped_data = json.load(f)
        logger.info(
            f"Loaded scraped NBA data: {_scraped_data['metadata']['total_teams']} teams, "
            f"{_scraped_data['metadata']['total_players']} players"
        )
        return _scraped_data
    except Exception as e:
        logger.error(f"Error loading scraped data: {e}")
        return None


def _get_team_key_from_scraped(team_name: str) -> str | None:
    """Get the canonical team key from scraped data."""
    data = _load_scraped_data()
    if not data:
        return None

    lower = team_name.lower().strip()

    # Check team_id_map for aliases
    if lower in data.get("team_id_map", {}):
        return data["team_id_map"][lower]

    # Check direct team names
    if lower in data.get("teams", {}):
        return lower

    return None


def _find_common_players_scraped(team1: str, team2: str) -> list[str]:
    """Find common players using scraped data."""
    data = _load_scraped_data()
    if not data:
        return []

    team1_key = _get_team_key_from_scraped(team1)
    team2_key = _get_team_key_from_scraped(team2)

    if not team1_key or not team2_key:
        logger.warning(f"Teams not found in scraped data: {team1}={team1_key}, {team2}={team2_key}")
        return []

    raw_players1 = data["teams"][team1_key]["players"]
    raw_players2 = data["teams"][team2_key]["players"]

    # Handle both old format (list of strings) and new format (list of dicts)
    if raw_players1 and isinstance(raw_players1[0], dict):
        players1 = {p["name"] for p in raw_players1}
    else:
        players1 = set(raw_players1)

    if raw_players2 and isinstance(raw_players2[0], dict):
        players2 = {p["name"] for p in raw_players2}
    else:
        players2 = set(raw_players2)

    common = players1 & players2
    logger.info(f"Found {len(common)} common players between {team1} and {team2} (scraped data)")

    return sorted(common)


@lru_cache(maxsize=100)
def _get_team_id(team_name: str) -> int | None:
    """Get NBA team ID from team name."""
    if not _teams_module:
        return None

    try:
        # Try full name first
        teams = _teams_module.find_teams_by_full_name(team_name)
        if teams:
            return teams[0]["id"]

        # Try nickname
        teams = _teams_module.find_teams_by_nickname(team_name)
        if teams:
            return teams[0]["id"]

        # Try city
        teams = _teams_module.find_teams_by_city(team_name)
        if teams:
            return teams[0]["id"]

    except Exception as e:
        logger.error(f"Error getting team ID for {team_name}: {e}")

    return None


@lru_cache(maxsize=50)
def _get_franchise_players(team_id: int) -> frozenset[str]:
    """Get all players who have played for a franchise (cached)."""
    if not _franchise_players_module:
        return frozenset()

    try:
        import time

        # Rate limiting - NBA.com throttles requests
        time.sleep(0.6)

        logger.info(f"Fetching franchise players for team ID {team_id}")
        franchise = _franchise_players_module.FranchisePlayers(team_id=team_id)
        df = franchise.get_data_frames()[0]

        if df.empty:
            return frozenset()

        # PLAYER column contains player names
        players = set(df["PLAYER"].tolist())
        logger.info(f"Found {len(players)} players for team ID {team_id}")
        return frozenset(players)

    except Exception as e:
        logger.error(f"Error fetching franchise players for team {team_id}: {e}")
        return frozenset()


def _find_common_players_cached(team1: str, team2: str) -> tuple[str, ...]:
    """Find common players between two teams using real API."""
    logger.info(f"Looking up common players for {team1} and {team2} via API")

    team1_id = _get_team_id(team1)
    team2_id = _get_team_id(team2)

    if not team1_id or not team2_id:
        logger.warning(f"Could not find team IDs: {team1}={team1_id}, {team2}={team2_id}")
        return ()

    players1 = _get_franchise_players(team1_id)
    players2 = _get_franchise_players(team2_id)

    common = players1 & players2
    logger.info(f"Found {len(common)} common players between {team1} and {team2}")

    return tuple(sorted(common))


# Lazy import to avoid slow startup
_nba_api_loaded = False
_players_module = None
_teams_module = None
_career_stats_module = None
_franchise_players_module = None


def _load_nba_api():
    """Lazy load nba_api modules."""
    global \
        _nba_api_loaded, \
        _players_module, \
        _teams_module, \
        _career_stats_module, \
        _franchise_players_module
    if not _nba_api_loaded:
        try:
            from nba_api.stats.endpoints import franchiseplayers, playercareerstats
            from nba_api.stats.static import players, teams

            _players_module = players
            _teams_module = teams
            _career_stats_module = playercareerstats
            _franchise_players_module = franchiseplayers
            _nba_api_loaded = True
            logger.info("nba_api loaded successfully")
        except ImportError:
            logger.warning("nba_api not available, using mock data")


class NBADataService:
    """Service for NBA player and team data lookups."""

    # Mock data for testing when nba_api is not available
    MOCK_TEAMS = {
        "los angeles lakers": ["LeBron James", "Anthony Davis", "Kobe Bryant", "Shaquille O'Neal"],
        "miami heat": ["LeBron James", "Dwyane Wade", "Chris Bosh", "Shaquille O'Neal"],
        "cleveland cavaliers": ["LeBron James", "Kyrie Irving", "Kevin Love"],
        "golden state warriors": ["Stephen Curry", "Klay Thompson", "Kevin Durant"],
        "brooklyn nets": ["Kevin Durant", "Kyrie Irving", "James Harden"],
        "boston celtics": ["Kyrie Irving", "Jayson Tatum", "Jaylen Brown", "Shaquille O'Neal"],
        "phoenix suns": ["Kevin Durant", "Devin Booker", "Chris Paul", "Shaquille O'Neal"],
        "orlando magic": ["Shaquille O'Neal", "Penny Hardaway"],
    }

    # Team name aliases
    TEAM_ALIASES = {
        "lakers": "los angeles lakers",
        "la lakers": "los angeles lakers",
        "heat": "miami heat",
        "cavs": "cleveland cavaliers",
        "warriors": "golden state warriors",
        "gsw": "golden state warriors",
        "nets": "brooklyn nets",
        "celtics": "boston celtics",
        "suns": "phoenix suns",
        "magic": "orlando magic",
    }

    def __init__(self) -> None:
        # Try to load scraped data first, then fall back to nba_api
        _load_scraped_data()
        _load_nba_api()

    def validate_club(self, team_name: str) -> bool:
        """Check if a team name is valid."""
        # Check scraped data first
        if _get_team_key_from_scraped(team_name):
            return True

        # Check mock data
        normalized = self._normalize_team_name(team_name)
        if normalized in self.MOCK_TEAMS:
            return True

        # Fall back to live API
        if _nba_api_loaded and _teams_module:
            try:
                teams = _teams_module.find_teams_by_full_name(team_name)
                if teams:
                    return True
                teams = _teams_module.find_teams_by_city(team_name)
                if teams:
                    return True
                teams = _teams_module.find_teams_by_nickname(team_name)
                return bool(teams)
            except Exception as e:
                logger.error(f"Error validating team: {e}")

        return False

    def normalize_club_name(self, team_name: str) -> str:
        """Normalize team name to standard format."""
        # Check scraped data first
        data = _load_scraped_data()
        if data:
            team_key = _get_team_key_from_scraped(team_name)
            if team_key and team_key in data["teams"]:
                return data["teams"][team_key]["full_name"]

        # Check mock data
        normalized = self._normalize_team_name(team_name)
        if normalized in self.MOCK_TEAMS:
            return normalized.title()

        # Fall back to live API
        if _nba_api_loaded and _teams_module:
            try:
                teams = _teams_module.find_teams_by_full_name(team_name)
                if teams:
                    return teams[0]["full_name"]
                teams = _teams_module.find_teams_by_city(team_name)
                if teams:
                    return teams[0]["full_name"]
                teams = _teams_module.find_teams_by_nickname(team_name)
                if teams:
                    return teams[0]["full_name"]
            except Exception as e:
                logger.error(f"Error normalizing team: {e}")

        return team_name.title()

    def normalize_player_name(self, player_name: str) -> str:
        """Normalize player name."""
        return player_name.strip().title()

    def find_common_players(self, team1: str, team2: str) -> list[str]:
        """Find players who played for both teams."""
        # Try scraped data first (fastest, comprehensive)
        if _load_scraped_data():
            result = _find_common_players_scraped(team1, team2)
            if result:
                return result

        # Use real NBA API if enabled and available
        if settings.use_real_nba_api and _nba_api_loaded:
            logger.info(f"Using real NBA API for {team1} vs {team2}")
            result = self._find_common_players_api(team1, team2)
            if result:
                return result
            logger.warning("Real API returned no results, falling back to mock data")

        # Fall back to mock data for quick lookup
        team1_normalized = self._normalize_team_name(team1)
        team2_normalized = self._normalize_team_name(team2)

        if team1_normalized in self.MOCK_TEAMS and team2_normalized in self.MOCK_TEAMS:
            players1 = set(self.MOCK_TEAMS[team1_normalized])
            players2 = set(self.MOCK_TEAMS[team2_normalized])
            return sorted(players1 & players2)

        return []

    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for lookups."""
        lower = team_name.lower().strip()
        return self.TEAM_ALIASES.get(lower, lower)

    def _find_common_players_api(self, team1: str, team2: str) -> list[str]:
        """Find common players using the actual nba_api."""
        # Use module-level cached function to avoid memory leaks
        return list(_find_common_players_cached(team1, team2))

    def get_club_players(self, team_name: str) -> list[str]:
        """Get all players who have played for a team."""
        # Try scraped data first
        data = _load_scraped_data()
        if data:
            team_key = _get_team_key_from_scraped(team_name)
            if team_key and team_key in data["teams"]:
                raw_players = data["teams"][team_key]["players"]
                # Handle both old format (list of strings) and new format (list of dicts)
                if raw_players and isinstance(raw_players[0], dict):
                    return [p["name"] for p in raw_players]
                return raw_players

        # Fall back to mock data
        normalized = self._normalize_team_name(team_name)
        if normalized in self.MOCK_TEAMS:
            return self.MOCK_TEAMS[normalized]

        return []

    def get_club_info(self, team_name: str) -> dict | None:
        """Get full team info including logos.

        Returns:
            Dict with keys: id, full_name, nickname, city, abbreviation, logo, logo_small
            Or None if team not found.
        """
        data = _load_scraped_data()
        if data:
            team_key = _get_team_key_from_scraped(team_name)
            if team_key and team_key in data["teams"]:
                team = data["teams"][team_key]
                return {
                    "id": team["id"],
                    "full_name": team["full_name"],
                    "nickname": team["nickname"],
                    "city": team["city"],
                    "abbreviation": team["abbreviation"],
                    "logo": team.get("logo"),
                    "logo_small": team.get("logo_small"),
                }
        return None

    def get_all_clubs(self) -> list[dict]:
        """Get all teams with their info for autocomplete/dropdown.

        Returns:
            List of team dicts with: full_name, nickname, abbreviation, logo_small
        """
        data = _load_scraped_data()
        if not data:
            # Return mock team names if no scraped data
            return [
                {"full_name": name.title(), "nickname": name.split()[-1].title()}
                for name in self.MOCK_TEAMS
            ]

        teams = []
        for team_data in data["teams"].values():
            teams.append(
                {
                    "full_name": team_data["full_name"],
                    "nickname": team_data["nickname"],
                    "abbreviation": team_data["abbreviation"],
                    "logo_small": team_data.get("logo_small"),
                }
            )

        return sorted(teams, key=lambda t: t["full_name"])

    def get_player_details(self, player_names: list[str]) -> list[dict]:
        """Get player details including image URLs for a list of player names.

        For JSON-based data, we can look up external_id from the scraped data
        and generate NBA.com image URLs.

        Args:
            player_names: List of player names to look up.

        Returns:
            List of dicts with: name, image_url (may be None).
        """
        data = _load_scraped_data()
        if not data:
            # No scraped data, return names without images
            return [{"name": name, "image_url": None} for name in player_names]

        # Build lookup from scraped data: name -> external_id
        player_lookup: dict[str, str | None] = {}
        for team_data in data.get("teams", {}).values():
            for player in team_data.get("players", []):
                if isinstance(player, dict):
                    # New format with name and external_id
                    name_lower = player["name"].lower()
                    player_lookup[name_lower] = player.get("external_id")
                else:
                    # Old format (string only) - no external_id
                    player_lookup[player.lower()] = None

        result = []
        for name in player_names:
            name_lower = name.lower()
            external_id = player_lookup.get(name_lower)
            if external_id:
                # Generate NBA.com image URL
                image_url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{external_id}.png"
            else:
                image_url = None
            result.append({"name": name, "image_url": image_url})

        return result
