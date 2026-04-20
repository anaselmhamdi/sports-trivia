#!/usr/bin/env python3
"""Generate deterministic mock NBA player metadata.

This is a **development / testing** tool. It reads the existing team roster
from `nba_players.json` and synthesizes plausible-looking awards, draft info,
career data, and coach rosters — enough for the grid generator to produce
balanced 3×3 boards across all category families without the real scrape.

The real scraper (Basketball-Reference) is in `scrape_nba_metadata.py` and
produces the same JSON schema; the seeder consumes either interchangeably.

Usage:
    uv run python scripts/generate_mock_nba_metadata.py

Output: src/sports_trivia/data/nba_player_metadata.json
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "src" / "sports_trivia" / "data"
NBA_SOURCE = DATA_DIR / "nba_players.json"
METADATA_OUTPUT = DATA_DIR / "nba_player_metadata.json"

# Marquee coaches and their era (for plausible player assignment).
MOCK_COACHES: list[dict] = [
    {"name": "Phil Jackson", "era": (1989, 2011)},
    {"name": "Gregg Popovich", "era": (1996, 2023)},
    {"name": "Pat Riley", "era": (1981, 2008)},
    {"name": "Red Auerbach", "era": (1950, 1966)},
    {"name": "Larry Brown", "era": (1976, 2010)},
    {"name": "Don Nelson", "era": (1976, 2010)},
    {"name": "Jerry Sloan", "era": (1979, 2011)},
    {"name": "Rick Adelman", "era": (1988, 2014)},
    {"name": "George Karl", "era": (1984, 2016)},
    {"name": "Doc Rivers", "era": (1999, 2024)},
    {"name": "Steve Kerr", "era": (2014, 2024)},
    {"name": "Erik Spoelstra", "era": (2008, 2024)},
]

# Rough real-world proportions: out of ~5k distinct modern players...
AWARD_RATES: dict[str, float] = {
    "MVP": 0.008,  # ~40 unique MVPs across history
    "DPOY": 0.008,
    "ROY": 0.015,
    "6MOY": 0.015,
    "FMVP": 0.008,
    "ALL_STAR": 0.05,  # ~250 unique All-Stars
    "ALL_NBA": 0.04,
    "ALL_DEF": 0.04,
    "CHAMPION": 0.12,  # ~12% of all players won a ring (rosters, not just stars)
}

# Draft distribution across players
DRAFT_HAVING_INFO_RATE = 0.65  # 65% have draft info
UNDRAFTED_RATE_AMONG_DRAFT = 0.20  # 20% of those were undrafted

CAREER_INFO_RATE = 0.55  # 55% get career stats

# Birthplace distribution (rough real-world approximation)
BIRTHPLACE_DIST = {
    "USA": 0.80,
    "FRA": 0.02,
    "SRB": 0.01,
    "ESP": 0.01,
    "CAN": 0.02,
    "AUS": 0.01,
    "GER": 0.01,
    "LTU": 0.005,
    "GRC": 0.005,
    "ARG": 0.01,
    "BRA": 0.005,
    "DOM": 0.005,
    "NGA": 0.005,
    "CMR": 0.005,
    "TUR": 0.005,
    "ITA": 0.005,
    "CRO": 0.005,
    "SVN": 0.005,
}

EUROPEAN_COUNTRIES: set[str] = {
    "FRA",
    "ESP",
    "GER",
    "ITA",
    "GRC",
    "SRB",
    "CRO",
    "SVN",
    "LTU",
    "TUR",
}

# Season stats — only assign to players who have career info
SEASONS_PER_CAREER_MIN = 3
SEASONS_PER_CAREER_MAX = 18

SEED = 42


def _load_source_players() -> list[dict]:
    """Flatten the team-centric JSON into a deduplicated player list."""
    if not NBA_SOURCE.exists():
        raise FileNotFoundError(f"Missing {NBA_SOURCE} — run scrape_nba_data.py first.")

    with NBA_SOURCE.open() as f:
        data = json.load(f)

    seen: set[str] = set()
    players: list[dict] = []
    for team_info in data.get("teams", {}).values():
        for raw in team_info.get("players", []):
            if isinstance(raw, str):
                name, ext = raw, None
            else:
                name, ext = raw["name"], raw.get("external_id")
            if name in seen:
                continue
            seen.add(name)
            players.append({"name": name, "external_id": ext})

    logger.info("Found %d unique NBA players across franchises", len(players))
    return players


def _synth_awards(rng: random.Random, players: list[dict]) -> list[dict]:
    """Generate award rows. Players can win the same award multiple years."""
    rows: list[dict] = []
    current_year = datetime.utcnow().year
    for player in players:
        for award, rate in AWARD_RATES.items():
            if rng.random() >= rate:
                continue
            # How many times did they win? 1-5 for multi-year awards, 1 otherwise.
            max_wins = 5 if award in {"ALL_STAR", "ALL_NBA", "ALL_DEF", "CHAMPION"} else 3
            wins = rng.randint(1, max_wins)
            years = rng.sample(range(1950, current_year + 1), k=min(wins, current_year - 1950))
            for year in years:
                rows.append(
                    {
                        "player_name": player["name"],
                        "award": award,
                        "year": year,
                    }
                )
    logger.info("Generated %d award rows", len(rows))
    return rows


def _synth_draft(rng: random.Random, players: list[dict]) -> list[dict]:
    """Generate draft info rows."""
    rows: list[dict] = []
    for player in players:
        if rng.random() >= DRAFT_HAVING_INFO_RATE:
            continue
        if rng.random() < UNDRAFTED_RATE_AMONG_DRAFT:
            rows.append(
                {
                    "player_name": player["name"],
                    "year": rng.randint(1970, 2023),
                    "overall_pick": None,
                    "undrafted": True,
                }
            )
            continue
        rows.append(
            {
                "player_name": player["name"],
                "year": rng.randint(1950, 2023),
                "overall_pick": rng.randint(1, 60),
                "undrafted": False,
            }
        )
    logger.info("Generated %d draft rows", len(rows))
    return rows


def _synth_career(rng: random.Random, players: list[dict]) -> list[dict]:
    """Generate career-span + stat rows."""
    rows: list[dict] = []
    for player in players:
        if rng.random() >= CAREER_INFO_RATE:
            continue
        first = rng.randint(1950, 2020)
        span = rng.randint(3, 20)
        last = min(first + span, 2024)
        rows.append(
            {
                "player_name": player["name"],
                "first_year": first,
                "last_year": last,
                "career_ppg": round(rng.uniform(2.0, 30.0), 1),
                "career_rpg": round(rng.uniform(1.0, 15.0), 1),
                "career_apg": round(rng.uniform(0.5, 11.0), 1),
                "career_spg": round(rng.uniform(0.1, 3.0), 1),
                "career_bpg": round(rng.uniform(0.1, 4.0), 1),
            }
        )
    logger.info("Generated %d career rows", len(rows))
    return rows


def _synth_birthplaces(rng: random.Random, players: list[dict]) -> list[dict]:
    """Assign a birth country to every player based on BIRTHPLACE_DIST."""
    countries = list(BIRTHPLACE_DIST.keys())
    weights = list(BIRTHPLACE_DIST.values())
    rows: list[dict] = []
    for p in players:
        country = rng.choices(countries, weights=weights, k=1)[0]
        rows.append(
            {
                "player_name": p["name"],
                "birth_country": country,
                "is_european": country in EUROPEAN_COUNTRIES,
            }
        )
    logger.info(
        "Generated %d birthplace rows (european=%d, non-USA=%d)",
        len(rows),
        sum(1 for r in rows if r["is_european"]),
        sum(1 for r in rows if r["birth_country"] != "USA"),
    )
    return rows


def _synth_seasons(rng: random.Random, career_rows: list[dict]) -> list[dict]:
    """One row per player × season across their career span.

    Each season is independently drawn with a plausible distribution so the
    "+N stat sur une saison" categories get enough qualifiers. A player's
    peak season is somewhere in the middle of their career.
    """
    out: list[dict] = []
    for c in career_rows:
        first = c["first_year"]
        last = c["last_year"]
        span = max(1, last - first + 1)
        # Shape: peak near year (first + span/2), lower at the edges.
        peak_year = first + span // 2
        for year in range(first, last + 1):
            distance = abs(year - peak_year)
            # Bell-ish falloff: peak stats close to 1.0 multiplier, edges 0.5.
            k = max(0.5, 1.0 - 0.05 * distance)
            out.append(
                {
                    "player_name": c["player_name"],
                    "year": year,
                    "ppg": round(rng.uniform(2.0, 30.0) * k, 1),
                    "rpg": round(rng.uniform(1.0, 14.0) * k, 1),
                    "apg": round(rng.uniform(0.3, 11.0) * k, 1),
                    "spg": round(rng.uniform(0.1, 3.0) * k, 1),
                    "bpg": round(rng.uniform(0.1, 4.0) * k, 1),
                }
            )
    logger.info("Generated %d season rows", len(out))
    return out


def _synth_coaches(rng: random.Random, career_rows: list[dict]) -> list[dict]:
    """Assign ~30-70 players to each coach whose career overlaps the coach's era."""
    career_by_name = {r["player_name"]: r for r in career_rows}
    coaches_out: list[dict] = []
    for coach in MOCK_COACHES:
        start, end = coach["era"]
        eligible = [
            name
            for name, c in career_by_name.items()
            if c["first_year"] <= end and c["last_year"] >= start
        ]
        if not eligible:
            continue
        sample_size = min(len(eligible), rng.randint(30, 70))
        coaches_out.append(
            {
                "name": coach["name"],
                "headshot_url": None,
                "players": sorted(rng.sample(eligible, sample_size)),
            }
        )
    logger.info("Generated %d coach rows", len(coaches_out))
    return coaches_out


def generate_metadata() -> dict:
    rng = random.Random(SEED)
    players = _load_source_players()

    awards = _synth_awards(rng, players)
    draft = _synth_draft(rng, players)
    career = _synth_career(rng, players)
    seasons = _synth_seasons(rng, career)
    birthplaces = _synth_birthplaces(rng, players)
    coaches = _synth_coaches(rng, career)

    return {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "source": "mock",
            "seed": SEED,
            "players_scanned": len(players),
        },
        "awards": awards,
        "draft": draft,
        "career": career,
        "seasons": seasons,
        "birthplaces": birthplaces,
        "coaches": coaches,
    }


def main() -> None:
    data = generate_metadata()
    METADATA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with METADATA_OUTPUT.open("w") as f:
        json.dump(data, f, indent=2)
    logger.info(
        "Wrote %s (awards=%d draft=%d career=%d seasons=%d birthplaces=%d coaches=%d)",
        METADATA_OUTPUT,
        len(data["awards"]),
        len(data["draft"]),
        len(data["career"]),
        len(data["seasons"]),
        len(data["birthplaces"]),
        len(data["coaches"]),
    )


if __name__ == "__main__":
    main()
