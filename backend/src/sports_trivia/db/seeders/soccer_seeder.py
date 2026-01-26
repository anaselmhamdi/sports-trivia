"""Soccer data seeder.

Loads soccer club and player data from JSON file into the database.
"""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from sports_trivia.db.models import Club, ClubAlias, Player
from sports_trivia.db.seeders.base import BaseSeeder

logger = logging.getLogger(__name__)

# Path to soccer data file
SOCCER_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "soccer_players.json"


class SoccerSeeder(BaseSeeder):
    """Seeder for soccer clubs and players."""

    def __init__(self, engine, fetch_logos: bool = False):
        super().__init__(engine)
        self.fetch_logos = fetch_logos

    @property
    def league_name(self) -> str:
        return "Soccer"

    @property
    def league_slug(self) -> str:
        return "soccer"

    def seed(self) -> None:
        """Seed soccer data from JSON file."""
        if not SOCCER_DATA_FILE.exists():
            logger.warning(f"Soccer data file not found: {SOCCER_DATA_FILE}")
            return

        # Load JSON data
        with open(SOCCER_DATA_FILE) as f:
            data = json.load(f)

        logger.info(
            f"Loading soccer data: {data['metadata']['total_clubs']} clubs, "
            f"{data['metadata']['total_players']} players"
        )

        with Session(self.engine) as session:
            league = self.get_or_create_league(session)

            # Track players by normalized name to avoid duplicates
            players_cache: dict[str, Player] = {}

            # Process each club
            clubs_data = data.get("clubs", {})
            for club_count, (club_key, club_info) in enumerate(clubs_data.items(), start=1):
                club = self._create_or_update_club(session, league.id, club_key, club_info)

                # Add players - support both old format (list of strings) and new format (list of dicts)
                for player_data in club_info.get("players", []):
                    player = self._get_or_create_player(session, player_data, players_cache)
                    if player not in club.players:
                        club.players.append(player)

                # Commit in batches to manage memory
                if club_count % 50 == 0:
                    session.commit()
                    logger.info(f"Processed {club_count} clubs...")

            # Process aliases from club_id_map (auto-generated from abbreviation/alternate_names)
            club_id_map = data.get("club_id_map", {})
            for alias, canonical_key in club_id_map.items():
                if alias != canonical_key:
                    self._add_alias(session, league.id, canonical_key, alias)

            session.commit()
            logger.info(
                f"Soccer seeding complete: {len(clubs_data)} clubs, {len(players_cache)} players"
            )

    def _create_or_update_club(
        self, session: Session, league_id: int, key: str, info: dict
    ) -> Club:
        """Create or update a club."""
        # Check if club exists
        existing = session.query(Club).filter(Club.league_id == league_id, Club.key == key).first()

        if existing:
            # Update existing
            existing.external_id = info.get("id")
            existing.full_name = info["full_name"]
            existing.abbreviation = info.get("abbreviation")
            existing.alternate_names = info.get("alternate_names")
            existing.country = info.get("country")
            existing.badge = info.get("badge")
            existing.logo = info.get("logo")
            return existing

        # Create new
        club = Club(
            league_id=league_id,
            key=key,
            external_id=info.get("id"),
            full_name=info["full_name"],
            abbreviation=info.get("abbreviation"),
            alternate_names=info.get("alternate_names"),
            country=info.get("country"),
            badge=info.get("badge"),
            logo=info.get("logo"),
        )
        session.add(club)
        session.flush()
        return club

    def _get_or_create_player(
        self, session: Session, player_data: str | dict, cache: dict[str, Player]
    ) -> Player:
        """Get or create a player, using cache for efficiency.

        Supports both old format (string) and new format (dict with name, external_id, image_url).
        """
        # Handle both string and dict format
        if isinstance(player_data, str):
            name = player_data
            external_id = None
            image_url = None
        else:
            name = player_data["name"]
            external_id = player_data.get("external_id")
            image_url = player_data.get("image_url")

        normalized = self.normalize_key(name)

        if normalized in cache:
            # Update existing player with new fields if provided
            existing = cache[normalized]
            if external_id and not existing.external_id:
                existing.external_id = external_id
            if image_url and not existing.image_url:
                existing.image_url = image_url
            return existing

        # Check database
        existing = session.query(Player).filter(Player.name_normalized == normalized).first()
        if existing:
            # Update existing player with new fields if provided
            if external_id and not existing.external_id:
                existing.external_id = external_id
            if image_url and not existing.image_url:
                existing.image_url = image_url
            cache[normalized] = existing
            return existing

        # Create new
        player = Player(
            name=self.normalize_name(name),
            name_normalized=normalized,
            external_id=external_id,
            image_url=image_url,
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
            # Not an error - just means the target club isn't in the dataset
            logger.debug(f"Club not found for alias: {canonical_key} -> {alias}")
            return

        club_alias = ClubAlias(
            club_id=club.id,
            league_id=league_id,
            alias=alias,
            alias_normalized=normalized_alias,
        )
        session.add(club_alias)
