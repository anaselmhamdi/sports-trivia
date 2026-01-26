"""Database seeders for loading sports data."""

from sports_trivia.db.seeders.base import BaseSeeder
from sports_trivia.db.seeders.nba_seeder import NBASeeder
from sports_trivia.db.seeders.soccer_seeder import SoccerSeeder

__all__ = ["BaseSeeder", "NBASeeder", "SoccerSeeder"]
