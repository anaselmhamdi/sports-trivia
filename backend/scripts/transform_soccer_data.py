#!/usr/bin/env python3
"""Transform soccer CSV data into JSON format.

Processes player profiles and transfer history to create a club → players mapping.
Optionally fetches logos from TheSportsDB API.

Usage:
    uv run python scripts/transform_soccer_data.py [--with-logos]

Input files:
    - src/sports_trivia/data/soccer_player_profiles.csv
    - src/sports_trivia/data/soccer_transfers.csv

Output file:
    - src/sports_trivia/data/soccer_players.json
"""

import argparse
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Path configuration
DATA_DIR = Path(__file__).parent.parent / "src" / "sports_trivia" / "data"
PLAYER_PROFILES_CSV = DATA_DIR / "soccer_player_profiles.csv"
TRANSFERS_CSV = DATA_DIR / "soccer_transfers.csv"
OUTPUT_FILE = DATA_DIR / "soccer_players.json"

# TheSportsDB API (free tier)
SPORTSDB_API_BASE = "https://www.thesportsdb.com/api/v1/json/3"

# Major league IDs for bulk fetching (much faster than individual searches)
# IDs from TheSportsDB - each ID must be unique
MAJOR_LEAGUE_IDS = {
    # Top 5 Leagues
    4328: "English Premier League",
    4335: "La Liga",
    4331: "Bundesliga",
    4332: "Serie A",
    4334: "Ligue 1",
    # Second Divisions
    4329: "English Championship",
    4336: "La Liga 2",
    4337: "2. Bundesliga",
    4338: "Serie B",
    4339: "Ligue 2",
    # Other European
    4344: "Primeira Liga",  # Portugal
    4340: "Scottish Premiership",
    4356: "Belgian Pro League",
    4354: "Austrian Bundesliga",
    4353: "Swiss Super League",
    4355: "Argentine Primera",
    # Americas
    4351: "Brasileirao",
    4346: "MLS",
    4352: "Liga MX",
}

# Retry configuration for API calls
MAX_RETRIES = 3
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 30
BASE_REQUEST_DELAY = 1.0  # 1 request per second to avoid rate limiting

# Filtering configuration
MIN_PLAYERS_PER_CLUB = 10
TOP_CLUB_LIMIT = 500


def clean_player_name(name: str) -> str:
    """Remove ID suffix from player name.

    Transfermarkt data has names like "Lionel Messi (28003)".
    Returns just "Lionel Messi".
    """
    cleaned = re.sub(r"\s*\(\d+\)$", "", name)
    return cleaned.strip()


# Pattern to match youth/reserve team suffixes
# Matches: U17, U18, U19, U20, U21, U23, B, II, Youth, Reserves, etc.
YOUTH_TEAM_PATTERN = re.compile(
    r"\s+(U-?\d{2}|B|II|III|Youth|Reserves?|Academy|Juniors?|Juvenil|Sub-?\d{2}|Primavera|Berretti)$",
    re.IGNORECASE,
)


def normalize_club_name_to_parent(club_name: str) -> tuple[str, bool]:
    """Normalize youth/reserve team names to their parent club.

    Args:
        club_name: Original club name (e.g., "Benfica U19", "Barcelona B")

    Returns:
        Tuple of (normalized_name, was_youth_team)
        e.g., ("Benfica", True) or ("Manchester United", False)
    """
    # Check if it's a youth/reserve team
    match = YOUTH_TEAM_PATTERN.search(club_name)
    if match:
        parent_name = club_name[: match.start()].strip()
        return parent_name, True
    return club_name, False


def load_player_profiles() -> pd.DataFrame:
    """Load player profiles CSV."""
    logger.info(f"Loading player profiles from {PLAYER_PROFILES_CSV}")
    df = pd.read_csv(
        PLAYER_PROFILES_CSV,
        usecols=["player_id", "player_name", "player_image_url"],
        dtype={"player_id": int},
    )
    logger.info(f"Loaded {len(df)} player profiles")
    return df


def load_transfers() -> pd.DataFrame:
    """Load transfer history CSV."""
    logger.info(f"Loading transfers from {TRANSFERS_CSV}")
    df = pd.read_csv(
        TRANSFERS_CSV,
        usecols=["player_id", "from_team_id", "from_team_name", "to_team_id", "to_team_name"],
        dtype={"player_id": int, "from_team_id": "Int64", "to_team_id": "Int64"},
    )
    logger.info(f"Loaded {len(df)} transfer records")
    return df


def build_player_map(profiles_df: pd.DataFrame) -> dict[int, dict]:
    """Build player_id → {name, external_id, image_url} mapping with cleaned names."""
    valid = profiles_df.dropna(subset=["player_name"])
    player_map = {}
    for _, row in valid.iterrows():
        player_id = row["player_id"]
        player_name = clean_player_name(row["player_name"])
        image_url = row.get("player_image_url") if pd.notna(row.get("player_image_url")) else None
        if player_name:  # Skip empty names
            player_map[player_id] = {
                "name": player_name,
                "external_id": str(player_id),
                "image_url": image_url,
            }
    logger.info(f"Built player map with {len(player_map)} entries")
    return player_map


def build_club_players_map(
    transfers_df: pd.DataFrame, player_map: dict[int, dict]
) -> dict[str, dict]:
    """Build club_name → {id, full_name, player_ids} mapping.

    Youth/reserve teams (U17, U19, B teams, etc.) are merged into their parent clubs.
    """
    clubs: dict[str, dict] = {}
    youth_teams_merged = 0

    logger.info("Processing transfer records...")
    total = len(transfers_df)

    def add_player_to_club(club_id: int, club_name: str, player_id: int) -> None:
        nonlocal youth_teams_merged

        # Normalize youth team names to parent club
        normalized_name, is_youth = normalize_club_name_to_parent(club_name)
        if is_youth:
            youth_teams_merged += 1

        key = normalized_name.lower().strip()

        if key not in clubs:
            clubs[key] = {"id": club_id, "full_name": normalized_name, "player_ids": set()}
        clubs[key]["player_ids"].add(player_id)

    for idx, row in transfers_df.iterrows():
        if idx % 200000 == 0:
            logger.info(f"  Processed {idx:,} / {total:,} transfers")

        player_id = row["player_id"]
        if player_id not in player_map:
            continue

        # Process "from" club
        if pd.notna(row["from_team_id"]) and pd.notna(row["from_team_name"]):
            add_player_to_club(
                int(row["from_team_id"]),
                row["from_team_name"],
                player_id,
            )

        # Process "to" club
        if pd.notna(row["to_team_id"]) and pd.notna(row["to_team_name"]):
            add_player_to_club(
                int(row["to_team_id"]),
                row["to_team_name"],
                player_id,
            )

    logger.info(
        f"Found {len(clubs)} unique clubs ({youth_teams_merged:,} youth team entries merged)"
    )
    return clubs


def convert_ids_to_player_details(
    clubs: dict[str, dict], player_map: dict[int, dict]
) -> dict[str, dict]:
    """Convert player IDs to player detail objects with name, external_id, and image_url."""
    for club_data in clubs.values():
        player_ids = club_data.pop("player_ids")
        players = []
        seen_names = set()
        for pid in player_ids:
            if pid in player_map:
                player_info = player_map[pid]
                name = player_info["name"]
                if name not in seen_names:
                    seen_names.add(name)
                    players.append(
                        {
                            "name": name,
                            "external_id": player_info["external_id"],
                            "image_url": player_info["image_url"],
                        }
                    )
        # Sort by name for consistent ordering
        club_data["players"] = sorted(players, key=lambda p: p["name"])
    return clubs


def filter_clubs(clubs: dict[str, dict]) -> dict[str, dict]:
    """Filter to valid clubs with sufficient players.

    Prioritizes major clubs to ensure famous teams like Real Madrid
    are included even if they have fewer transfer records than some
    lower-league teams.
    """
    # Major clubs that MUST be included if they exist in the data
    # These are the most recognizable clubs that players expect to see
    priority_clubs = {
        # La Liga
        "real madrid",
        "barcelona",
        "atlético madrid",
        "atletico madrid",
        "sevilla",
        "valencia",
        "villarreal",
        "real sociedad",
        "athletic bilbao",
        # Premier League
        "manchester united",
        "liverpool",
        "chelsea",
        "arsenal",
        "manchester city",
        "tottenham",
        "tottenham hotspur",
        "everton",
        "newcastle",
        "west ham",
        "aston villa",
        "leicester city",
        # Serie A
        "juventus",
        "inter",
        "ac milan",
        "napoli",
        "roma",
        "lazio",
        "fiorentina",
        "atalanta",
        # Bundesliga
        "bayern munich",
        "bayern münchen",
        "borussia dortmund",
        "rb leipzig",
        "bayer leverkusen",
        "schalke 04",
        # Ligue 1
        "paris sg",
        "paris saint-germain",
        "olympique lyon",
        "olympique marseille",
        "monaco",
        "lille",
        # Other major
        "benfica",
        "porto",
        "sporting cp",
        "ajax",
        "psv",
        "feyenoord",
        "galatasaray",
        "fenerbahce",
        "besiktas",
        "celtic",
        "rangers",
        "boca juniors",
        "river plate",
        "flamengo",
        "corinthians",
        "santos",
    }

    # Exclude non-club entries
    excluded = {"retired", "unknown", "career break", "without club"}

    filtered = {
        key: data
        for key, data in clubs.items()
        if len(data.get("players", [])) >= MIN_PLAYERS_PER_CLUB
        and key not in excluded
        and "without club" not in key
        # Note: Youth/reserve teams (U19, B, II, etc.) are now merged into parent clubs
        # during build_club_players_map, so no need to filter them here
    }
    logger.info(f"Filtered to {len(filtered)} clubs with >={MIN_PLAYERS_PER_CLUB} players")

    # Start with priority clubs that exist in the data
    result = {}
    for key in priority_clubs:
        if key in filtered:
            result[key] = filtered[key]

    priority_count = len(result)
    logger.info(f"Added {priority_count} priority clubs")

    # Fill remaining slots with top clubs by player count
    remaining_slots = TOP_CLUB_LIMIT - len(result)
    if remaining_slots > 0:
        other_clubs = [(k, v) for k, v in filtered.items() if k not in result]
        other_clubs.sort(key=lambda x: len(x[1]["players"]), reverse=True)
        for key, data in other_clubs[:remaining_slots]:
            result[key] = data

    logger.info(
        f"Selected {len(result)} clubs total ({priority_count} priority + {len(result) - priority_count} by player count)"
    )

    return result


class RateLimitError(Exception):
    """Raised when API returns 429."""

    pass


@retry(
    retry=retry_if_exception_type((RateLimitError, httpx.TimeoutException)),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def fetch_league_teams(league_id: int, client: httpx.Client) -> list[dict]:
    """Fetch all teams in a league from TheSportsDB API."""
    response = client.get(
        f"{SPORTSDB_API_BASE}/lookup_all_teams.php",
        params={"id": league_id},
    )

    if response.status_code == 429:
        raise RateLimitError(f"Rate limited for league {league_id}")

    response.raise_for_status()
    data = response.json()

    return data.get("teams") or []


@retry(
    retry=retry_if_exception_type((RateLimitError, httpx.TimeoutException)),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def search_team(club_name: str, client: httpx.Client) -> dict | None:
    """Search for a single team (fallback for clubs not in major leagues)."""
    response = client.get(
        f"{SPORTSDB_API_BASE}/searchteams.php",
        params={"t": club_name},
    )

    if response.status_code == 429:
        raise RateLimitError(f"Rate limited for {club_name}")

    response.raise_for_status()
    data = response.json()

    if data.get("teams"):
        return data["teams"][0]
    return None


def build_logo_cache(client: httpx.Client) -> dict[str, dict]:
    """Build a cache of team logos from major leagues (bulk fetch)."""
    cache: dict[str, dict] = {}

    logger.info(f"Fetching teams from {len(MAJOR_LEAGUE_IDS)} major leagues...")

    for league_id, league_name in MAJOR_LEAGUE_IDS.items():
        try:
            time.sleep(BASE_REQUEST_DELAY)
            teams = fetch_league_teams(league_id, client)

            for team in teams:
                team_name = team.get("strTeam", "").lower().strip()
                alt_name = team.get("strTeamAlternate", "").lower().strip()

                logo_info = {
                    "badge": team.get("strBadge"),
                    "logo": team.get("strLogo"),
                    "country": team.get("strCountry"),
                }

                if team_name:
                    cache[team_name] = logo_info
                if alt_name:
                    for alt in alt_name.split(","):
                        cache[alt.strip()] = logo_info

            logger.info(f"  {league_name}: {len(teams)} teams")
        except Exception as e:
            logger.warning(f"Could not fetch {league_name}: {e}")

    logger.info(f"Cached {len(cache)} team entries from major leagues")
    return cache


def enrich_with_logos(clubs: dict[str, dict]) -> dict[str, dict]:
    """Fetch logos, abbreviations, and alternate names for each club.

    Uses TheSportsDB search endpoint with rate limiting.
    Takes ~8-10 minutes for 500 clubs.
    """
    logger.info(f"Enriching {len(clubs)} clubs with logos and metadata...")
    found = 0
    not_found = 0

    with httpx.Client(timeout=15.0) as client:
        for i, (_key, club_data) in enumerate(clubs.items()):
            if i % 50 == 0:
                logger.info(f"  Progress: {i}/{len(clubs)} ({found} found)")

            # Rate limit to avoid 429 errors
            time.sleep(BASE_REQUEST_DELAY)

            try:
                team = search_team(club_data["full_name"], client)
                if team:
                    found += 1
                    # Logos
                    club_data["badge"] = team.get("strBadge")
                    club_data["logo"] = team.get("strLogo")
                    # Abbreviation (e.g., "PSG", "FCB")
                    club_data["abbreviation"] = team.get("strTeamShort")
                    # Alternate names (comma-separated, e.g., "PSG, Paris Saint-Germain")
                    club_data["alternate_names"] = team.get("strTeamAlternate")
                    # Other metadata
                    if team.get("strCountry"):
                        club_data["country"] = team["strCountry"]
                else:
                    not_found += 1
            except Exception as e:
                logger.debug(f"Could not fetch data for {club_data['full_name']}: {e}")
                not_found += 1

    logger.info(f"Finished: {found}/{len(clubs)} clubs enriched, {not_found} not found")
    return clubs


def build_aliases(clubs: dict[str, dict]) -> dict[str, str]:
    """Build club name aliases from fetched data.

    Auto-generates aliases from:
    - Club key and full name
    - Abbreviation (strTeamShort from TheSportsDB, e.g., "PSG")
    - Alternate names (strTeamAlternate, e.g., "Paris Saint-Germain, PSG")

    No hardcoded aliases needed - all come from the data source.
    """
    aliases: dict[str, str] = {}

    for key, club_data in clubs.items():
        full_name = club_data["full_name"]

        # Base aliases: key and full name
        aliases[key] = key
        aliases[full_name.lower()] = key

        # Add abbreviation as alias (e.g., "PSG" -> "paris sg")
        abbreviation = club_data.get("abbreviation")
        if abbreviation:
            aliases[abbreviation.lower()] = key

        # Add all alternate names as aliases
        alternate_names = club_data.get("alternate_names")
        if alternate_names:
            for alt in alternate_names.split(","):
                alt_clean = alt.strip().lower()
                if alt_clean and alt_clean not in aliases:
                    aliases[alt_clean] = key

    logger.info(f"Generated {len(aliases)} aliases from data source")
    return aliases


def save_output(clubs: dict[str, dict], aliases: dict[str, str]) -> None:
    """Save processed data to JSON."""
    data = {
        "metadata": {
            "processed_at": datetime.utcnow().isoformat(),
            "total_clubs": len(clubs),
            "total_players": sum(len(c["players"]) for c in clubs.values()),
        },
        "clubs": clubs,
        "club_id_map": aliases,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved to {OUTPUT_FILE}")
    logger.info(f"Total clubs: {data['metadata']['total_clubs']}")
    logger.info(f"Total players: {data['metadata']['total_players']}")


def main(fetch_logos: bool = False) -> None:
    """Run the transformation pipeline."""
    logger.info("Starting soccer data transformation...")

    # Check input files exist
    if not PLAYER_PROFILES_CSV.exists():
        logger.error(f"Player profiles not found: {PLAYER_PROFILES_CSV}")
        logger.error("Run download_soccer_data.py first")
        return

    if not TRANSFERS_CSV.exists():
        logger.error(f"Transfers not found: {TRANSFERS_CSV}")
        logger.error("Run download_soccer_data.py first")
        return

    # Load data
    profiles_df = load_player_profiles()
    transfers_df = load_transfers()

    # Transform
    player_map = build_player_map(profiles_df)
    clubs = build_club_players_map(transfers_df, player_map)
    clubs = convert_ids_to_player_details(clubs, player_map)
    clubs = filter_clubs(clubs)

    # Optionally fetch logos
    if fetch_logos:
        clubs = enrich_with_logos(clubs)
    else:
        logger.info("Skipping logo fetching (use --with-logos to enable)")

    # Build aliases and save
    aliases = build_aliases(clubs)
    save_output(clubs, aliases)

    logger.info("Transformation complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transform soccer data to JSON")
    parser.add_argument("--with-logos", action="store_true", help="Fetch logos from TheSportsDB")
    args = parser.parse_args()

    main(fetch_logos=args.with_logos)
