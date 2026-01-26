"""Base seeder class with common utilities."""

import logging
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from sports_trivia.db.models import League

logger = logging.getLogger(__name__)


class BaseSeeder(ABC):
    """Abstract base class for data seeders."""

    def __init__(self, engine: Engine):
        self.engine = engine

    @property
    @abstractmethod
    def league_name(self) -> str:
        """Human-readable league name (e.g., 'NBA')."""
        ...

    @property
    @abstractmethod
    def league_slug(self) -> str:
        """URL-friendly league identifier (e.g., 'nba')."""
        ...

    @abstractmethod
    def seed(self) -> None:
        """Seed the database with data."""
        ...

    def get_or_create_league(self, session: Session) -> League:
        """Get existing league or create new one.

        Args:
            session: Database session.

        Returns:
            League instance.
        """
        stmt = select(League).where(League.slug == self.league_slug)
        league = session.execute(stmt).scalar_one_or_none()

        if league:
            logger.info(f"Found existing league: {self.league_name}")
            return league

        league = League(name=self.league_name, slug=self.league_slug)
        session.add(league)
        session.flush()
        logger.info(f"Created league: {self.league_name}")
        return league

    def normalize_name(self, name: str) -> str:
        """Normalize a name for consistent storage.

        Args:
            name: Raw name string.

        Returns:
            Cleaned and normalized name.
        """
        return name.strip()

    def normalize_key(self, name: str) -> str:
        """Create a lowercase key for lookups.

        Args:
            name: Raw name string.

        Returns:
            Lowercase key suitable for matching.
        """
        return name.lower().strip()
