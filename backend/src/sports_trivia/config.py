"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server config
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # API-Football (soccer data)
    api_football_key: str = ""

    # Game settings
    default_timer_seconds: int = 60
    max_points_per_round: int = 100

    # NBA API settings
    use_real_nba_api: bool = False  # Set True to use real NBA API lookups

    # Data source: "db" for SQLite database, "json" for JSON files
    data_source: str = "json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
