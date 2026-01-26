"""NBA data seeder.

Loads NBA team and player data from JSON file into the database.
"""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from sports_trivia.db.models import Club, ClubAlias, Player
from sports_trivia.db.seeders.base import BaseSeeder

logger = logging.getLogger(__name__)

# Path to NBA data file
NBA_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "nba_players.json"


class NBASeeder(BaseSeeder):
    """Seeder for NBA teams and players."""

    @property
    def league_name(self) -> str:
        return "NBA"

    @property
    def league_slug(self) -> str:
        return "nba"

    def seed(self) -> None:
        """Seed NBA data from JSON file."""
        if not NBA_DATA_FILE.exists():
            logger.warning(f"NBA data file not found: {NBA_DATA_FILE}")
            return

        # Load JSON data
        with open(NBA_DATA_FILE) as f:
            data = json.load(f)

        logger.info(
            f"Loading NBA data: {data['metadata']['total_teams']} teams, "
            f"{data['metadata']['total_players']} players"
        )

        with Session(self.engine) as session:
            league = self.get_or_create_league(session)

            # Track players by normalized name to avoid duplicates
            players_cache: dict[str, Player] = {}

            # Process each team
            teams_data = data.get("teams", {})
            for team_key, team_info in teams_data.items():
                club = self._create_or_update_club(session, league.id, team_key, team_info)

                # Add players - support both old format (list of strings) and new format (list of dicts)
                for player_data in team_info.get("players", []):
                    player = self._get_or_create_player(session, player_data, players_cache)
                    if player not in club.players:
                        club.players.append(player)

            # Process aliases from team_id_map
            team_id_map = data.get("team_id_map", {})
            for alias, canonical_key in team_id_map.items():
                if alias != canonical_key:
                    self._add_alias(session, league.id, canonical_key, alias)

            session.commit()
            logger.info(
                f"NBA seeding complete: {len(teams_data)} teams, {len(players_cache)} players"
            )

    def _create_or_update_club(
        self, session: Session, league_id: int, key: str, info: dict
    ) -> Club:
        """Create or update a club/team."""
        # Check if club exists
        existing = session.query(Club).filter(Club.league_id == league_id, Club.key == key).first()

        if existing:
            # Update existing
            existing.external_id = info.get("id")
            existing.full_name = info["full_name"]
            existing.nickname = info.get("nickname")
            existing.city = info.get("city")
            existing.abbreviation = info.get("abbreviation")
            existing.logo = info.get("logo")
            existing.logo_small = info.get("logo_small")
            return existing

        # Create new
        club = Club(
            league_id=league_id,
            key=key,
            external_id=info.get("id"),
            full_name=info["full_name"],
            nickname=info.get("nickname"),
            city=info.get("city"),
            abbreviation=info.get("abbreviation"),
            logo=info.get("logo"),
            logo_small=info.get("logo_small"),
        )
        session.add(club)
        session.flush()
        return club

    def _get_or_create_player(
        self, session: Session, player_data: str | dict, cache: dict[str, Player]
    ) -> Player:
        """Get or create a player, using cache for efficiency.

        Supports both old format (string) and new format (dict with name, external_id).
        """
        # Handle both string and dict format
        if isinstance(player_data, str):
            name = player_data
            external_id = None
        else:
            name = player_data["name"]
            external_id = player_data.get("external_id")

        normalized = self.normalize_key(name)

        if normalized in cache:
            # Update existing player with external_id if provided
            existing = cache[normalized]
            if external_id and not existing.external_id:
                existing.external_id = external_id
            return existing

        # Check database
        existing = session.query(Player).filter(Player.name_normalized == normalized).first()
        if existing:
            # Update existing player with external_id if provided
            if external_id and not existing.external_id:
                existing.external_id = external_id
            cache[normalized] = existing
            return existing

        # Create new (image_url is generated from external_id for NBA)
        player = Player(
            name=self.normalize_name(name),
            name_normalized=normalized,
            external_id=external_id,
        )
        session.add(player)
        session.flush()
        cache[normalized] = player
        return player

    def _add_alias(self, session: Session, league_id: int, canonical_key: str, alias: str) -> None:
        """Add an alias for a club (league-scoped)."""
        normalized_alias = self.normalize_key(alias)

        # Check if alias already exists for this league
        existing = (
            session.query(ClubAlias)
            .filter(
                ClubAlias.league_id == league_id,
                ClubAlias.alias_normalized == normalized_alias,
            )
            .first()
        )
        if existing:
            return

        # Find the club
        club = (
            session.query(Club)
            .filter(Club.league_id == league_id, Club.key == canonical_key)
            .first()
        )
        if not club:
            logger.warning(f"Club not found for alias: {canonical_key} -> {alias}")
            return

        club_alias = ClubAlias(
            club_id=club.id,
            league_id=league_id,
            alias=alias,
            alias_normalized=normalized_alias,
        )
        session.add(club_alias)
