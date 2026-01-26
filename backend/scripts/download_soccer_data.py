#!/usr/bin/env python3
"""Download soccer data from GitHub.

Downloads player profiles and transfer history CSVs from the football-datasets repo.

Usage:
    uv run python scripts/download_soccer_data.py

Output files:
    - src/sports_trivia/data/soccer_player_profiles.csv
    - src/sports_trivia/data/soccer_transfers.csv
"""

import logging
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Output directory
DATA_DIR = Path(__file__).parent.parent / "src" / "sports_trivia" / "data"

# GitHub URLs (using media URL for LFS files)
PLAYER_PROFILES_URL = "https://raw.githubusercontent.com/salimt/football-datasets/main/datalake/transfermarkt/player_profiles/player_profiles.csv"
TRANSFERS_URL = "https://media.githubusercontent.com/media/salimt/football-datasets/main/datalake/transfermarkt/transfer_history/transfer_history.csv"


def download_file(url: str, output_path: Path) -> None:
    """Download a file from URL to the specified path."""
    logger.info(f"Downloading {output_path.name}...")

    with (
        httpx.Client(timeout=300.0, follow_redirects=True) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))

        with open(output_path, "wb") as f:
            downloaded = 0
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = (downloaded / total) * 100
                    print(f"\r  Progress: {pct:.1f}% ({downloaded:,} / {total:,} bytes)", end="")

    print()  # New line after progress
    logger.info(f"Saved to {output_path}")


def main() -> None:
    """Download all soccer data files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Download player profiles
    profiles_path = DATA_DIR / "soccer_player_profiles.csv"
    download_file(PLAYER_PROFILES_URL, profiles_path)

    # Download transfer history
    transfers_path = DATA_DIR / "soccer_transfers.csv"
    download_file(TRANSFERS_URL, transfers_path)

    logger.info("All downloads complete!")


if __name__ == "__main__":
    main()
