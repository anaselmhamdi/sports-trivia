"""Repository pattern for database operations.

Provides a clean interface for common database queries.
"""

import logging

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from sports_trivia.db.models import Club, ClubAlias, League, Player

logger = logging.getLogger(__name__)

# Minimum fuzzy match score (0-100) to accept
FUZZY_MATCH_THRESHOLD = 80


class SportsRepository:
    """Database operations for sports data."""

    def __init__(self, session: Session):
        self.session = session

    def get_league_by_slug(self, slug: str) -> League | None:
        """Get a league by its slug.

        Args:
            slug: The league slug (e.g., "nba", "soccer").

        Returns:
            League instance or None if not found.
        """
        stmt = select(League).where(League.slug == slug)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_club_by_name(self, league_slug: str, name: str) -> Club | None:
        """Find a club by name or alias within a league.

        Uses exact matching first, then falls back to fuzzy matching.

        Args:
            league_slug: The league slug (e.g., "nba", "soccer").
            name: The club name to search for (case-insensitive).

        Returns:
            Club instance or None if not found.
        """
        normalized = name.lower().strip()

        # Get league first for league-scoped lookups
        league = self.get_league_by_slug(league_slug)
        if not league:
            return None

        # First, check aliases (most common lookup path)
        # Aliases are league-scoped, so same alias can exist in different leagues
        alias_stmt = (
            select(Club)
            .join(ClubAlias)
            .where(ClubAlias.league_id == league.id)
            .where(ClubAlias.alias_normalized == normalized)
        )
        club = self.session.execute(alias_stmt).scalar_one_or_none()
        if club:
            return club

        # Then check direct key match
        key_stmt = select(Club).where(Club.league_id == league.id).where(Club.key == normalized)
        club = self.session.execute(key_stmt).scalar_one_or_none()
        if club:
            return club

        # Fallback: fuzzy match against all club names and aliases
        return self._fuzzy_match_club(league_slug, normalized)

    def _fuzzy_match_club(self, league_slug: str, query: str) -> Club | None:
        """Find a club using fuzzy string matching.

        Args:
            league_slug: The league slug.
            query: The search query (normalized).

        Returns:
            Best matching Club or None if no good match found.
        """
        # Get all clubs for this league
        clubs = self.get_all_clubs(league_slug)
        if not clubs:
            return None

        # Build list of (name, club) tuples for matching
        candidates: list[tuple[str, Club]] = []
        for club in clubs:
            # Add full name
            candidates.append((club.full_name.lower(), club))
            # Add key
            candidates.append((club.key, club))
            # Add nickname/abbreviation if available
            if club.nickname:
                candidates.append((club.nickname.lower(), club))
            if club.abbreviation:
                candidates.append((club.abbreviation.lower(), club))

        # Also add aliases
        alias_stmt = (
            select(ClubAlias, Club).join(Club).join(League).where(League.slug == league_slug)
        )
        for alias, club in self.session.execute(alias_stmt).all():
            candidates.append((alias.alias_normalized, club))

        if not candidates:
            return None

        # Find best match using rapidfuzz
        names = [c[0] for c in candidates]
        result = process.extractOne(
            query,
            names,
            scorer=fuzz.WRatio,
            score_cutoff=FUZZY_MATCH_THRESHOLD,
        )

        if result:
            matched_name, score, index = result
            matched_club = candidates[index][1]
            logger.info(f"Fuzzy matched '{query}' -> '{matched_club.full_name}' (score: {score})")
            return matched_club

        logger.warning(f"No fuzzy match found for '{query}' in {league_slug}")
        return None

    def get_club_by_id(self, club_id: int) -> Club | None:
        """Get a club by its ID.

        Args:
            club_id: The club's database ID.

        Returns:
            Club instance or None if not found.
        """
        return self.session.get(Club, club_id)

    def find_common_players(self, club1_id: int, club2_id: int) -> list[Player]:
        """Find players who played for both clubs.

        Uses SQL intersection for efficient query.

        Args:
            club1_id: First club's database ID.
            club2_id: Second club's database ID.

        Returns:
            List of Player instances who played for both clubs.
        """
        # Get club1's player IDs
        club1 = self.session.get(Club, club1_id)
        club2 = self.session.get(Club, club2_id)

        if not club1 or not club2:
            return []

        # Find intersection using relationship
        player_ids_1 = {p.id for p in club1.players}
        player_ids_2 = {p.id for p in club2.players}
        common_ids = player_ids_1 & player_ids_2

        if not common_ids:
            return []

        # Fetch player objects
        stmt = select(Player).where(Player.id.in_(common_ids)).order_by(Player.name)
        return list(self.session.execute(stmt).scalars().all())

    def get_club_players(self, club_id: int) -> list[Player]:
        """Get all players for a club.

        Args:
            club_id: The club's database ID.

        Returns:
            List of Player instances.
        """
        club = self.session.get(Club, club_id)
        if not club:
            return []
        return sorted(club.players, key=lambda p: p.name)

    def get_all_clubs(self, league_slug: str) -> list[Club]:
        """Get all clubs for a league.

        Args:
            league_slug: The league slug (e.g., "nba", "soccer").

        Returns:
            List of Club instances sorted by full_name.
        """
        stmt = select(Club).join(League).where(League.slug == league_slug).order_by(Club.full_name)
        return list(self.session.execute(stmt).scalars().all())

    def get_or_create_player(self, name: str) -> Player:
        """Get existing player or create new one.

        Args:
            name: The player's name.

        Returns:
            Player instance (existing or newly created).
        """
        normalized = name.lower().strip()

        stmt = select(Player).where(Player.name_normalized == normalized)
        player = self.session.execute(stmt).scalar_one_or_none()

        if player:
            return player

        player = Player(name=name, name_normalized=normalized)
        self.session.add(player)
        return player

    def add_player_to_club(self, player: Player, club: Club) -> None:
        """Add a player to a club's roster.

        Args:
            player: The Player instance.
            club: The Club instance.
        """
        if player not in club.players:
            club.players.append(player)

    def add_club_alias(self, club: Club, alias: str) -> ClubAlias | None:
        """Add an alias for a club.

        Args:
            club: The Club instance.
            alias: The alias string.

        Returns:
            ClubAlias instance or None if alias already exists globally.
        """
        normalized = alias.lower().strip()

        # Check if alias already exists
        stmt = select(ClubAlias).where(ClubAlias.alias_normalized == normalized)
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing:
            logger.debug(f"Alias '{alias}' already exists for club {existing.club_id}")
            return None

        club_alias = ClubAlias(club=club, alias=alias, alias_normalized=normalized)
        self.session.add(club_alias)
        return club_alias

    def get_players_by_names(self, names: list[str]) -> list[Player]:
        """Get players by their names (case-insensitive).

        Args:
            names: List of player names to look up.

        Returns:
            List of Player instances found (may be fewer than input if some not found).
        """
        if not names:
            return []

        normalized_names = [n.lower().strip() for n in names]
        stmt = select(Player).where(Player.name_normalized.in_(normalized_names))
        return list(self.session.execute(stmt).scalars().all())
