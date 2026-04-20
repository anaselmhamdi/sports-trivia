#!/usr/bin/env python3
"""Scrape NBA player metadata from Basketball-Reference.

Produces `src/sports_trivia/data/nba_player_metadata.json` with:
- Awards (MVP, DPOY, ROY, 6MOY, FMVP, All-Star, All-NBA, All-Defense, Champion)
- Draft info (year, overall pick, undrafted)
- Career span + averages (first/last year, PPG, RPG, APG, SPG, BPG)
- Marquee coaches + players they coached

The seeder (`db/seeders/metadata_seeder.py`) loads this JSON into the
`player_awards`, `player_draft`, `player_career`, `coaches`, and
`coach_players` tables. The grid category system then discovers which
families have data and registers the matching categories.

This script is idempotent — re-running overwrites the JSON. Raw HTML is
cached under `data/cache/bbref/` so retries are cheap.

Usage:
    uv run python scripts/scrape_nba_metadata.py              # full run
    uv run python scripts/scrape_nba_metadata.py --limit 5    # smoke test
    uv run python scripts/scrape_nba_metadata.py --only awards,draft

Respect Basketball-Reference's 1 req/3s guideline — a full run takes ~45 min.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

try:
    import httpx
except ImportError:  # pragma: no cover - fallback is only relevant when actually scraping
    httpx = None  # type: ignore[assignment]

try:
    from bs4 import BeautifulSoup  # noqa: F401 — only needed for live scraping
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.basketball-reference.com"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "bbref"
OUTPUT_FILE = (
    Path(__file__).parent.parent / "src" / "sports_trivia" / "data" / "nba_player_metadata.json"
)
REQUEST_DELAY_SECONDS = 3.0  # BBR rate limit recommendation

# URL map — one entry per award type
AWARD_URLS: dict[str, str] = {
    "MVP": "/awards/mvp.html",
    "DPOY": "/awards/dpoy.html",
    "ROY": "/awards/roy.html",
    "6MOY": "/awards/smoy.html",
    "FMVP": "/awards/finals_mvp.html",
    "ALL_STAR": "/awards/all_star_by_player.html",
    "ALL_NBA": "/awards/all_league.html",
    "ALL_DEF": "/awards/all_defense.html",
}

# Marquee coaches (slugs → display names). BBR uses these slugs in /coaches/{slug}.html
COACH_SLUGS: dict[str, str] = {
    "jacksph01c": "Phil Jackson",
    "popovgr01c": "Gregg Popovich",
    "rileypa01c": "Pat Riley",
    "auerbre99c": "Red Auerbach",
    "brownla01c": "Larry Brown",
    "nelsodo01c": "Don Nelson",
    "sloanje01c": "Jerry Sloan",
    "adelmri99c": "Rick Adelman",
    "karlge01c": "George Karl",
    "riverdo99c": "Doc Rivers",
    "kerrst01c": "Steve Kerr",
    "spoelre01c": "Erik Spoelstra",
}

# Years to scrape draft data for (1950 = earliest reliable year on BBR)
DRAFT_YEARS = list(range(1950, datetime.utcnow().year))


@dataclass
class ScrapeState:
    """Collected data across all scraping stages."""

    awards: list[dict] = field(default_factory=list)
    draft: list[dict] = field(default_factory=list)
    career: list[dict] = field(default_factory=list)
    coaches: list[dict] = field(default_factory=list)


# ---------- HTTP + cache ----------


def _cache_path(url: str) -> Path:
    key = re.sub(r"[^a-zA-Z0-9_-]+", "_", url.replace(BASE_URL, "").strip("/"))
    return CACHE_DIR / f"{key}.html"


def fetch(url: str) -> str:
    """Fetch a BBR page with on-disk caching. Respects rate limit."""
    if httpx is None:
        raise RuntimeError("httpx not installed. Add `pip install httpx beautifulsoup4`.")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = _cache_path(url)
    if cache.exists():
        return cache.read_text()

    time.sleep(REQUEST_DELAY_SECONDS)
    logger.info("GET %s", url)
    resp = httpx.get(url, timeout=30.0, headers={"User-Agent": "sports-trivia/1.0"})
    resp.raise_for_status()
    cache.write_text(resp.text)
    return resp.text


# ---------- parsers ----------


def _parse_season_to_year(season: str) -> int | None:
    """'2022-23' → 2023, '1999-00' → 2000."""
    m = re.match(r"(\d{4})-(\d{2})", season.strip())
    if not m:
        return None
    start = int(m.group(1))
    return start + 1


def scrape_awards(state: ScrapeState, limit: int | None = None) -> None:
    """Scrape each award page. Implementer note: BBR's award tables use
    id='{award}_NBA' and have columns Season / Lg / Player. Parse the <a>
    inside the Player cell — it's the canonical name."""
    if BeautifulSoup is None:
        raise RuntimeError("bs4 not installed.")

    for idx, (award, path) in enumerate(AWARD_URLS.items()):
        if limit is not None and idx >= limit:
            break
        html = fetch(urljoin(BASE_URL, path))
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id=re.compile(r"(NBA|winners)"))
        if table is None:
            logger.warning("No table found for %s at %s", award, path)
            continue
        for row in table.select("tbody tr"):
            season_cell = row.find("th", {"data-stat": "season"}) or row.find(
                "td", {"data-stat": "season"}
            )
            player_cell = row.find("td", {"data-stat": "player"})
            if not season_cell or not player_cell:
                continue
            year = _parse_season_to_year(season_cell.get_text(strip=True))
            player = player_cell.get_text(strip=True)
            if year and player:
                state.awards.append({"player_name": player, "award": award, "year": year})
    logger.info("Collected %d award rows", len(state.awards))


def scrape_draft(state: ScrapeState, limit: int | None = None) -> None:
    """Scrape per-year draft pages. Table columns of interest:
    'overall_pick' (td[data-stat='pick_overall']) and 'player' (td[data-stat='player'])."""
    if BeautifulSoup is None:
        raise RuntimeError("bs4 not installed.")

    years = DRAFT_YEARS[:limit] if limit is not None else DRAFT_YEARS
    for year in years:
        path = f"/draft/NBA_{year}.html"
        try:
            html = fetch(urljoin(BASE_URL, path))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch %s — skipping", path)
            continue
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="stats")
        if table is None:
            continue
        for row in table.select("tbody tr"):
            pick_cell = row.find("td", {"data-stat": "pick_overall"})
            name_cell = row.find("td", {"data-stat": "player"})
            if not name_cell:
                continue
            pick = pick_cell.get_text(strip=True) if pick_cell else ""
            player = name_cell.get_text(strip=True)
            if not player:
                continue
            try:
                overall = int(pick) if pick else None
            except ValueError:
                overall = None
            state.draft.append(
                {
                    "player_name": player,
                    "year": year,
                    "overall_pick": overall,
                    "undrafted": False,
                }
            )
    logger.info("Collected %d draft rows across %d years", len(state.draft), len(years))


def scrape_career(state: ScrapeState) -> None:  # noqa: ARG001 — state populated by implementer
    """Career stats require per-player pages — too expensive to scrape in bulk.
    Recommended alternative: parse the career leaders pages for PPG/RPG/APG
    (https://www.basketball-reference.com/leaders/per_career.html etc.) which
    gives the top ~250 per metric in one fetch.

    TODO: implementer should populate state.career by:
      1. Fetching /leaders/pts_per_g_career.html → PPG leaders
      2. Fetching /leaders/trb_per_g_career.html → RPG leaders
      3. Fetching /leaders/ast_per_g_career.html → APG leaders
      4. Merging rows by player name; storing first/last year from each player's
         header (or from /players/{last-initial}/{slug}.html if needed).
    """
    logger.warning(
        "scrape_career is a skeleton — implement leaderboard parsing or per-player pages."
    )


def scrape_coaches(state: ScrapeState) -> None:
    """For each marquee coach, fetch /coaches/{slug}.html and pull the players-coached table."""
    if BeautifulSoup is None:
        raise RuntimeError("bs4 not installed.")

    for slug, display_name in COACH_SLUGS.items():
        path = f"/coaches/{slug}.html"
        try:
            html = fetch(urljoin(BASE_URL, path))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch %s — skipping coach", path)
            continue
        soup = BeautifulSoup(html, "html.parser")
        # Headshot: <div class="media-item"><img src="..."></div>
        img = soup.select_one(".media-item img")
        headshot_url = img["src"] if img and img.has_attr("src") else None
        # Players-coached table id varies; try common patterns.
        table = soup.find("table", id=re.compile(r"players"))
        players: list[str] = []
        if table:
            for row in table.select("tbody tr"):
                cell = row.find("td", {"data-stat": "player"}) or row.find("th")
                if cell:
                    players.append(cell.get_text(strip=True))
        state.coaches.append(
            {"name": display_name, "headshot_url": headshot_url, "players": sorted(set(players))}
        )
    logger.info("Collected %d coach rosters", len(state.coaches))


# ---------- entry ----------


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape NBA metadata from Basketball-Reference")
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test: scrape a small subset")
    parser.add_argument(
        "--only",
        type=str,
        default="awards,draft,coaches",
        help="Comma-separated subset: awards,draft,career,coaches",
    )
    args = parser.parse_args()
    stages = {s.strip() for s in args.only.split(",")}

    state = ScrapeState()
    if "awards" in stages:
        scrape_awards(state, limit=args.limit)
    if "draft" in stages:
        scrape_draft(state, limit=args.limit)
    if "career" in stages:
        scrape_career(state)
    if "coaches" in stages:
        scrape_coaches(state)

    out = {
        "metadata": {
            "scraped_at": datetime.utcnow().isoformat(),
            "source": "basketball-reference",
            "stages": sorted(stages),
        },
        "awards": state.awards,
        "draft": state.draft,
        "career": state.career,
        "coaches": state.coaches,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, indent=2))
    logger.info(
        "Wrote %s (awards=%d draft=%d career=%d coaches=%d)",
        OUTPUT_FILE,
        len(state.awards),
        len(state.draft),
        len(state.career),
        len(state.coaches),
    )


if __name__ == "__main__":
    main()
