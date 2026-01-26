"""Database module for Sports Trivia.

Provides SQLAlchemy engine, session management, and model exports.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Database file location (alongside existing JSON files)
DATABASE_PATH = Path(__file__).parent.parent / "data" / "sports_trivia.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Module-level engine cache
_engine: Engine | None = None


def get_engine(echo: bool = False) -> Engine:
    """Get or create the SQLAlchemy engine.

    Args:
        echo: If True, log all SQL statements.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            echo=echo,
            connect_args={"check_same_thread": False},  # SQLite threading
        )
    return _engine


def get_session() -> Session:
    """Create a new database session.

    Returns:
        SQLAlchemy Session instance.
    """
    SessionLocal = sessionmaker(bind=get_engine())
    return SessionLocal()


# Re-export models and base for convenience
from sports_trivia.db.models import Base, Club, ClubAlias, ClubPlayer, League, Player  # noqa: E402

__all__ = [
    "DATABASE_PATH",
    "DATABASE_URL",
    "get_engine",
    "get_session",
    "Base",
    "League",
    "Club",
    "Player",
    "ClubPlayer",
    "ClubAlias",
]
