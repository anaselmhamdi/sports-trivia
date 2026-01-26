#!/usr/bin/env python3
"""ETL script to scrape NBA player data from nba_api and save locally.

This script fetches all franchise players for every NBA team and saves the data
to a JSON file that can be loaded by the NBADataService for fast lookups.

Usage:
    uv run python scripts/scrape_nba_data.py

The output file is saved to: src/sports_trivia/data/nba_players.json
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Output path for scraped data
DATA_DIR = Path(__file__).parent.parent / "src" / "sports_trivia" / "data"
OUTPUT_FILE = DATA_DIR / "nba_players.json"

# Rate limiting delay between API calls (NBA.com throttles requests)
REQUEST_DELAY_SECONDS = 0.6


def extract_teams() -> list[dict]:
    """Extract all NBA teams from nba_api."""
    from nba_api.stats.static import teams

    all_teams = teams.get_teams()
    logger.info(f"Found {len(all_teams)} NBA teams")
    return all_teams


def extract_franchise_players(team_id: int, team_name: str) -> list[dict]:
    """Extract all players who have played for a franchise.

    Returns list of player dicts with name and external_id for image URLs.
    """
    from nba_api.stats.endpoints import franchiseplayers

    try:
        time.sleep(REQUEST_DELAY_SECONDS)
        logger.info(f"Fetching players for {team_name} (ID: {team_id})")

        franchise = franchiseplayers.FranchisePlayers(team_id=team_id)
        df = franchise.get_data_frames()[0]

        if df.empty:
            logger.warning(f"No players found for {team_name}")
            return []

        # Return player dicts with name and external_id for image URLs
        players = []
        for _, row in df.iterrows():
            players.append(
                {
                    "name": row["PLAYER"],
                    "external_id": str(row["PERSON_ID"]),  # NBA API uses PERSON_ID
                }
            )
        logger.info(f"Found {len(players)} players for {team_name}")
        return players

    except Exception as e:
        logger.error(f"Error fetching players for {team_name}: {e}")
        return []


def get_team_logo_url(team_id: int, size: str = "L") -> str:
    """Get NBA team logo URL.

    Args:
        team_id: NBA team ID
        size: Logo size - "L" (large), "D" (default/medium), "S" (small)

    Returns:
        URL to the team's logo on NBA CDN
    """
    # NBA.com CDN pattern for team logos
    # Available sizes: L (large), D (default), S (small)
    return f"https://cdn.nba.com/logos/nba/{team_id}/global/{size}/logo.svg"


def transform_data(teams: list[dict], players_by_team: dict[int, list[dict]]) -> dict:
    """Transform raw data into the final structure.

    Players are stored as dicts with name and external_id for image URL generation.
    """
    data = {
        "metadata": {
            "scraped_at": datetime.utcnow().isoformat(),
            "total_teams": len(teams),
            "total_players": sum(len(p) for p in players_by_team.values()),
        },
        "teams": {},
        "team_id_map": {},
    }

    for team in teams:
        team_id = team["id"]
        full_name = team["full_name"]
        nickname = team["nickname"]
        city = team["city"]
        abbreviation = team["abbreviation"]

        players = players_by_team.get(team_id, [])

        # Store team data with logo URLs
        # Players are stored as dicts: [{name, external_id}, ...]
        data["teams"][full_name.lower()] = {
            "id": team_id,
            "full_name": full_name,
            "nickname": nickname,
            "city": city,
            "abbreviation": abbreviation,
            "logo": get_team_logo_url(team_id, "L"),
            "logo_small": get_team_logo_url(team_id, "S"),
            "players": players,
        }

        # Create lookup aliases
        data["team_id_map"][full_name.lower()] = full_name.lower()
        data["team_id_map"][nickname.lower()] = full_name.lower()
        data["team_id_map"][city.lower()] = full_name.lower()
        data["team_id_map"][abbreviation.lower()] = full_name.lower()

        # Common aliases
        if nickname.lower() == "cavaliers":
            data["team_id_map"]["cavs"] = full_name.lower()
        if nickname.lower() == "warriors":
            data["team_id_map"]["gsw"] = full_name.lower()
        if city.lower() == "los angeles" and nickname.lower() == "lakers":
            data["team_id_map"]["la lakers"] = full_name.lower()
        if city.lower() == "los angeles" and nickname.lower() == "clippers":
            data["team_id_map"]["la clippers"] = full_name.lower()

    return data


def load_data(data: dict) -> None:
    """Load (save) the transformed data to a JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved data to {OUTPUT_FILE}")
    logger.info(f"Total teams: {data['metadata']['total_teams']}")
    logger.info(f"Total players: {data['metadata']['total_players']}")


def run_etl() -> None:
    """Run the full ETL pipeline."""
    logger.info("Starting NBA data ETL...")

    # Extract
    teams = extract_teams()
    players_by_team: dict[int, list[dict]] = {}

    for team in teams:
        players = extract_franchise_players(team["id"], team["full_name"])
        players_by_team[team["id"]] = players

    # Transform
    data = transform_data(teams, players_by_team)

    # Load
    load_data(data)

    logger.info("ETL complete!")


if __name__ == "__main__":
    run_etl()
