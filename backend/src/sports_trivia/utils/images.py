"""Player image URL utilities.

Provides functions to generate player headshot URLs from various sources.
Supports multiple leagues with different image providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sports_trivia.db.models import Player

# League-specific URL patterns for player headshots
# {id} will be replaced with player.external_id
PLAYER_IMAGE_PATTERNS: dict[str, str] = {
    "nba": "https://cdn.nba.com/headshots/nba/latest/260x190/{id}.png",
    # Future leagues can be added here:
    # "nfl": "https://api.nfl.com/profilePicture/{id}",
    # "mlb": "https://securea.mlb.com/mlb/images/players/head_shot/{id}.jpg",
}


def get_player_image_url(player: Player, league_slug: str) -> str | None:
    """Get player image URL - prefer stored URL, fallback to pattern.

    Args:
        player: Player model instance with optional image_url and external_id.
        league_slug: League identifier (e.g., "nba", "soccer").

    Returns:
        Image URL string if available, None otherwise.
    """
    # Prefer direct stored URL (e.g., Transfermarkt URLs for soccer)
    if player.image_url:
        return player.image_url

    # Fallback to league-specific pattern if we have an external_id
    if not player.external_id:
        return None

    pattern = PLAYER_IMAGE_PATTERNS.get(league_slug)
    if pattern:
        return pattern.format(id=player.external_id)

    return None


def get_player_image_url_from_dict(player_data: dict, league_slug: str) -> str | None:
    """Get player image URL from a dict (for use without DB model).

    Args:
        player_data: Dict with optional 'image_url' and 'external_id' keys.
        league_slug: League identifier (e.g., "nba", "soccer").

    Returns:
        Image URL string if available, None otherwise.
    """
    # Prefer direct stored URL
    image_url = player_data.get("image_url")
    if image_url:
        return image_url

    # Fallback to league-specific pattern
    external_id = player_data.get("external_id")
    if not external_id:
        return None

    pattern = PLAYER_IMAGE_PATTERNS.get(league_slug)
    if pattern:
        return pattern.format(id=external_id)

    return None
