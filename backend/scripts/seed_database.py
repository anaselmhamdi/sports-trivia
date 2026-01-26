#!/usr/bin/env python3
"""Seed the database with fresh sports data.

Downloads data from sources, transforms it, and loads into SQLite.

Usage:
    uv run python scripts/seed_database.py [--nba] [--soccer] [--logos]

Options:
    --nba       Seed NBA data only
    --soccer    Seed soccer data only
    --logos     Fetch logos from TheSportsDB (slower)
    --reset     Drop and recreate all tables

Without options, seeds both NBA and soccer data without logos.

Examples:
    # Seed all data
    uv run python scripts/seed_database.py

    # Reset and reseed
    uv run python scripts/seed_database.py --reset

    # Seed only NBA
    uv run python scripts/seed_database.py --nba

    # Seed soccer with logos
    uv run python scripts/seed_database.py --soccer --logos
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sports_trivia.db import DATABASE_PATH, Base, get_engine
from sports_trivia.db.seeders import NBASeeder, SoccerSeeder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Seed the sports trivia database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--nba",
        action="store_true",
        help="Seed NBA data only",
    )
    parser.add_argument(
        "--soccer",
        action="store_true",
        help="Seed soccer data only",
    )
    parser.add_argument(
        "--logos",
        action="store_true",
        help="Fetch logos from TheSportsDB (slower)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose SQL logging",
    )
    args = parser.parse_args()

    # Get engine
    engine = get_engine(echo=args.verbose)

    logger.info(f"Database path: {DATABASE_PATH}")

    # Handle reset
    if args.reset:
        logger.info("Dropping all tables...")
        Base.metadata.drop_all(engine)

    # Create tables
    logger.info("Creating tables...")
    Base.metadata.create_all(engine)

    # Default: seed both if neither specified
    seed_nba = args.nba or (not args.nba and not args.soccer)
    seed_soccer = args.soccer or (not args.nba and not args.soccer)

    # Seed data
    if seed_nba:
        logger.info("Seeding NBA data...")
        NBASeeder(engine).seed()

    if seed_soccer:
        logger.info("Seeding soccer data...")
        SoccerSeeder(engine, fetch_logos=args.logos).seed()

    # Summary
    from sqlalchemy import text

    with engine.connect() as conn:
        leagues = conn.execute(text("SELECT COUNT(*) FROM leagues")).scalar()
        clubs = conn.execute(text("SELECT COUNT(*) FROM clubs")).scalar()
        players = conn.execute(text("SELECT COUNT(*) FROM players")).scalar()
        aliases = conn.execute(text("SELECT COUNT(*) FROM club_aliases")).scalar()

    logger.info("=" * 50)
    logger.info("Seeding complete!")
    logger.info(f"  Leagues: {leagues}")
    logger.info(f"  Clubs: {clubs}")
    logger.info(f"  Players: {players}")
    logger.info(f"  Aliases: {aliases}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
