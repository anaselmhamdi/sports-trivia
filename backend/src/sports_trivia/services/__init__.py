"""Services for the Sports Trivia game."""

import logging

from sports_trivia.config import settings
from sports_trivia.models import Sport
from sports_trivia.services.base import SportDataService
from sports_trivia.services.game_manager import GameManager
from sports_trivia.services.nba_data import NBADataService
from sports_trivia.services.room_manager import RoomManager
from sports_trivia.services.soccer_data import SoccerDataService

logger = logging.getLogger(__name__)

# Service registry for sport-specific data services
_services: dict[Sport, SportDataService] = {}


def register_service(sport: Sport, service: SportDataService) -> None:
    """Register a sport data service for a specific sport.

    Args:
        sport: The sport enum value.
        service: The service instance implementing SportDataService protocol.
    """
    _services[sport] = service


def get_service(sport: Sport) -> SportDataService:
    """Get the registered data service for a sport.

    Args:
        sport: The sport enum value.

    Returns:
        The registered SportDataService instance.

    Raises:
        KeyError: If no service is registered for the sport.
    """
    return _services[sport]


def _create_services() -> None:
    """Create and register services based on configuration.

    Uses database-backed services when data_source="db",
    otherwise falls back to JSON-based services.
    """
    if settings.data_source == "db":
        try:
            from sports_trivia.db import DATABASE_PATH
            from sports_trivia.services.db_data import NBADatabaseService, SoccerDatabaseService

            if DATABASE_PATH.exists():
                logger.info("Using database-backed data services")
                register_service(Sport.NBA, NBADatabaseService())
                register_service(Sport.SOCCER, SoccerDatabaseService())
                return
            else:
                logger.warning(
                    f"Database not found at {DATABASE_PATH}, "
                    "falling back to JSON services. Run seed_database.py first."
                )
        except ImportError as e:
            logger.warning(f"Could not import database services: {e}")

    # Default: JSON-based services
    logger.info("Using JSON-backed data services")
    register_service(Sport.NBA, NBADataService())
    register_service(Sport.SOCCER, SoccerDataService())


# Auto-register services on module import
_create_services()

__all__ = [
    "RoomManager",
    "GameManager",
    "SportDataService",
    "NBADataService",
    "SoccerDataService",
    "register_service",
    "get_service",
]
