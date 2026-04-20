"""NBA metadata seeder.

Loads awards, draft info, career stats, and coach rosters from
`nba_player_metadata.json` (produced by either `generate_mock_nba_metadata.py`
or `scrape_nba_metadata.py`) into the DB tables that power NBA Grid
categories.

Player names in the metadata JSON are matched to existing Player rows by
normalized name. Unknown names are skipped with a debug log — the NBA seeder
must have run first.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from sports_trivia.db.models import (
    Coach,
    CoachPlayer,
    Player,
    PlayerAward,
    PlayerCareer,
    PlayerDraft,
    PlayerSeason,
)

logger = logging.getLogger(__name__)

METADATA_FILE = Path(__file__).parent.parent.parent / "data" / "nba_player_metadata.json"


class NBAMetadataSeeder:
    """Seeds PlayerAward, PlayerDraft, PlayerCareer, Coach, CoachPlayer tables."""

    def __init__(self, engine: Engine, metadata_file: Path | None = None):
        self.engine = engine
        self.metadata_file = metadata_file or METADATA_FILE

    def seed(self) -> None:
        if not self.metadata_file.exists():
            logger.warning(
                "No metadata file at %s — skipping NBA metadata seeding. "
                "Run generate_mock_nba_metadata.py or scrape_nba_metadata.py.",
                self.metadata_file,
            )
            return

        with self.metadata_file.open() as f:
            data = json.load(f)

        logger.info("Loading NBA metadata from %s", self.metadata_file)

        with Session(self.engine) as session:
            player_lookup = self._build_player_lookup(session)

            awards_loaded = self._seed_awards(session, data.get("awards", []), player_lookup)
            draft_loaded = self._seed_draft(session, data.get("draft", []), player_lookup)
            career_loaded = self._seed_career(session, data.get("career", []), player_lookup)
            season_loaded = self._seed_seasons(session, data.get("seasons", []), player_lookup)
            birth_loaded = self._seed_birthplaces(
                session, data.get("birthplaces", []), player_lookup
            )
            coach_loaded, coach_player_loaded = self._seed_coaches(
                session, data.get("coaches", []), player_lookup
            )

            session.commit()

        logger.info(
            "NBA metadata seeding complete: awards=%d draft=%d career=%d seasons=%d birthplaces=%d coaches=%d coach_players=%d",
            awards_loaded,
            draft_loaded,
            career_loaded,
            season_loaded,
            birth_loaded,
            coach_loaded,
            coach_player_loaded,
        )

    def _build_player_lookup(self, session: Session) -> dict[str, int]:
        """Map normalized name -> player_id for all NBA players in the DB."""
        lookup: dict[str, int] = {}
        for player in session.query(Player).all():
            lookup[player.name_normalized] = player.id
        logger.info("Built player lookup with %d entries", len(lookup))
        return lookup

    def _resolve(self, name: str, lookup: dict[str, int]) -> int | None:
        normalized = name.lower().strip()
        pid = lookup.get(normalized)
        if pid is None:
            logger.debug("Metadata player not found in DB: %s", name)
        return pid

    def _seed_awards(self, session: Session, rows: list[dict], lookup: dict[str, int]) -> int:
        if not rows:
            return 0
        # Fresh load: drop existing rows so re-seeding is idempotent.
        session.query(PlayerAward).delete()
        loaded = 0
        for row in rows:
            pid = self._resolve(row.get("player_name", ""), lookup)
            if pid is None:
                continue
            session.add(
                PlayerAward(
                    player_id=pid,
                    award_name=row["award"],
                    year=row.get("year"),
                )
            )
            loaded += 1
        return loaded

    def _seed_draft(self, session: Session, rows: list[dict], lookup: dict[str, int]) -> int:
        if not rows:
            return 0
        session.query(PlayerDraft).delete()
        loaded = 0
        seen_pids: set[int] = set()
        for row in rows:
            pid = self._resolve(row.get("player_name", ""), lookup)
            if pid is None or pid in seen_pids:
                continue
            seen_pids.add(pid)
            session.add(
                PlayerDraft(
                    player_id=pid,
                    year=row.get("year"),
                    overall_pick=row.get("overall_pick"),
                    undrafted=bool(row.get("undrafted", False)),
                )
            )
            loaded += 1
        return loaded

    def _seed_career(self, session: Session, rows: list[dict], lookup: dict[str, int]) -> int:
        if not rows:
            return 0
        session.query(PlayerCareer).delete()
        loaded = 0
        seen_pids: set[int] = set()
        for row in rows:
            pid = self._resolve(row.get("player_name", ""), lookup)
            if pid is None or pid in seen_pids:
                continue
            seen_pids.add(pid)
            session.add(
                PlayerCareer(
                    player_id=pid,
                    first_year=row.get("first_year"),
                    last_year=row.get("last_year"),
                    career_ppg=row.get("career_ppg"),
                    career_rpg=row.get("career_rpg"),
                    career_apg=row.get("career_apg"),
                    career_spg=row.get("career_spg"),
                    career_bpg=row.get("career_bpg"),
                )
            )
            loaded += 1
        return loaded

    def _seed_seasons(self, session: Session, rows: list[dict], lookup: dict[str, int]) -> int:
        if not rows:
            return 0
        session.query(PlayerSeason).delete()
        loaded = 0
        for row in rows:
            pid = self._resolve(row.get("player_name", ""), lookup)
            if pid is None or row.get("year") is None:
                continue
            session.add(
                PlayerSeason(
                    player_id=pid,
                    year=row["year"],
                    ppg=row.get("ppg"),
                    rpg=row.get("rpg"),
                    apg=row.get("apg"),
                    spg=row.get("spg"),
                    bpg=row.get("bpg"),
                )
            )
            loaded += 1
        return loaded

    def _seed_birthplaces(self, session: Session, rows: list[dict], lookup: dict[str, int]) -> int:
        """Writes `birth_country` + `is_european` directly on the Player row."""
        if not rows:
            return 0
        loaded = 0
        for row in rows:
            pid = self._resolve(row.get("player_name", ""), lookup)
            if pid is None:
                continue
            player = session.get(Player, pid)
            if player is None:
                continue
            player.birth_country = row.get("birth_country")
            player.is_european = bool(row.get("is_european", False))
            loaded += 1
        return loaded

    def _seed_coaches(
        self, session: Session, rows: list[dict], lookup: dict[str, int]
    ) -> tuple[int, int]:
        if not rows:
            return 0, 0
        # Wipe prior coach tables.
        session.query(CoachPlayer).delete()
        session.query(Coach).delete()
        session.flush()

        coaches_loaded = 0
        links_loaded = 0
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            coach = Coach(
                name=name,
                name_normalized=name.lower().strip(),
                headshot_url=row.get("headshot_url"),
            )
            session.add(coach)
            session.flush()  # need coach.id for the link rows
            coaches_loaded += 1

            seen_pids: set[int] = set()
            for player_name in row.get("players", []):
                pid = self._resolve(player_name, lookup)
                if pid is None or pid in seen_pids:
                    continue
                seen_pids.add(pid)
                session.add(CoachPlayer(coach_id=coach.id, player_id=pid))
                links_loaded += 1
        return coaches_loaded, links_loaded
