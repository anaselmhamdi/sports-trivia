"""Integration tests for the NBA Grid pipeline.

Exercises the full stack below the WebSocket transport: metadata seeder →
category builder → grid generator → `GameManager.start_grid_game` →
`submit_grid_guess`. A TestClient-based WS test would cover the transport
layer too but introduces async-task lifecycle complications with sync
TestClient; the WS layer itself is a thin wrapper over these calls.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sports_trivia.db.models import Base, Player, PlayerAward, PlayerDraft
from sports_trivia.db.seeders import NBAMetadataSeeder, NBASeeder
from sports_trivia.models import GameMode, GamePhase, GameState, Room, Sport
from sports_trivia.models import Player as GamePlayer
from sports_trivia.services import grid_categories as grid_cats_module
from sports_trivia.services.game_manager import GameManager
from sports_trivia.services.grid_categories import build_all_categories


@pytest.fixture
def seeded_engine(tmp_path, monkeypatch):
    """Spin up an in-memory DB, seed it from slim NBA + metadata fixtures.

    Patches the seeder file paths and `get_session` so the live GameManager
    sees this in-memory DB when it later calls `get_session()`.
    """
    # Minimal NBA fixture — 3 marquee teams so the category builder finds them.
    nba_fixture = {
        "metadata": {"scraped_at": "test", "total_teams": 3, "total_players": 90},
        "team_id_map": {},
        "teams": {
            "los angeles lakers": {
                "id": 1,
                "full_name": "Los Angeles Lakers",
                "nickname": "Lakers",
                "city": "Los Angeles",
                "abbreviation": "LAL",
                "logo": "lakers.png",
                "logo_small": "lakers_s.png",
                "players": [
                    {"name": f"Laker Player {i}", "external_id": f"L{i}"} for i in range(40)
                ],
            },
            "boston celtics": {
                "id": 2,
                "full_name": "Boston Celtics",
                "nickname": "Celtics",
                "city": "Boston",
                "abbreviation": "BOS",
                "logo": "celtics.png",
                "logo_small": "celtics_s.png",
                "players": [
                    {"name": f"Celtic Player {i}", "external_id": f"B{i}"} for i in range(40)
                ],
            },
            "chicago bulls": {
                "id": 3,
                "full_name": "Chicago Bulls",
                "nickname": "Bulls",
                "city": "Chicago",
                "abbreviation": "CHI",
                "logo": "bulls.png",
                "logo_small": "bulls_s.png",
                "players": [
                    {"name": f"Bull Player {i}", "external_id": f"C{i}"} for i in range(40)
                ],
            },
        },
    }
    nba_file = tmp_path / "nba_players.json"
    nba_file.write_text(json.dumps(nba_fixture))

    # Metadata fixture — several award types + draft, designed so at-least-one
    # award × team intersection has ≥10 players.
    metadata: dict = {
        "metadata": {"source": "test"},
        "awards": [],
        "draft": [],
        "career": [],
        "coaches": [],
    }
    # Every player gets MVP + DPOY + FMVP so award categories overlap heavily
    # with teams — guarantees balance.
    for team_prefix in ("Laker", "Celtic", "Bull"):
        for i in range(40):
            for award in ("MVP", "DPOY", "FMVP", "ALL_STAR"):
                metadata["awards"].append(
                    {
                        "player_name": f"{team_prefix} Player {i}",
                        "award": award,
                        "year": 2000 + (i % 25),
                    }
                )
            metadata["draft"].append(
                {
                    "player_name": f"{team_prefix} Player {i}",
                    "year": 1990 + (i % 30),
                    "overall_pick": (i % 5) + 1,
                    "undrafted": False,
                }
            )
    meta_file = tmp_path / "nba_player_metadata.json"
    meta_file.write_text(json.dumps(metadata))

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    import sports_trivia.db.seeders.metadata_seeder as meta_seeder_mod
    import sports_trivia.db.seeders.nba_seeder as nba_seeder_mod

    monkeypatch.setattr(nba_seeder_mod, "NBA_DATA_FILE", nba_file)
    monkeypatch.setattr(meta_seeder_mod, "METADATA_FILE", meta_file)

    NBASeeder(engine).seed()
    NBAMetadataSeeder(engine, metadata_file=meta_file).seed()

    import sports_trivia.db as db_pkg

    monkeypatch.setattr(db_pkg, "get_session", lambda: SessionLocal())
    # Tests exercise award + draft families; flip the mock-data guard on for
    # the test session only.
    monkeypatch.setattr(grid_cats_module, "TRUST_METADATA_FAMILIES", True)
    return engine, SessionLocal


# ---------- seeder tests ----------


class TestSeederFixture:
    def test_awards_loaded(self, seeded_engine) -> None:
        _, SessionLocal = seeded_engine
        session = SessionLocal()
        try:
            # 40 players × 4 awards × 3 teams = 480 award rows
            assert session.query(PlayerAward).count() == 480
        finally:
            session.close()

    def test_draft_one_per_player(self, seeded_engine) -> None:
        _, SessionLocal = seeded_engine
        session = SessionLocal()
        try:
            rows = session.query(PlayerDraft).all()
            assert len(rows) == 120  # 40 × 3 unique players
            ids = [r.player_id for r in rows]
            assert len(ids) == len(set(ids))
        finally:
            session.close()

    def test_players_loaded(self, seeded_engine) -> None:
        _, SessionLocal = seeded_engine
        session = SessionLocal()
        try:
            assert session.query(Player).count() == 120
        finally:
            session.close()

    def test_categories_cover_expected_families(self, seeded_engine) -> None:
        _, SessionLocal = seeded_engine
        session = SessionLocal()
        try:
            families = {c.family for c in build_all_categories(session)}
            assert {"team", "award", "draft"}.issubset(families)
        finally:
            session.close()


# ---------- game-manager pipeline test ----------


@pytest.mark.usefixtures("seeded_engine")
class TestGridGameStart:
    """Verify that `start_grid_game` works end-to-end against real seeded data."""

    def test_start_grid_game_succeeds(self) -> None:
        room = Room(
            code="GRID99",
            sport=Sport.NBA,
            mode=GameMode.NBA_GRID,
            host_id="p1",
            game_state=GameState(phase=GamePhase.WAITING_FOR_PLAYERS),
        )
        room.players = [
            GamePlayer(id="p1", name="Alice"),
            GamePlayer(id="p2", name="Bob"),
        ]

        gm = GameManager()
        result = gm.start_grid_game(room, "p1")
        assert result["success"], result.get("error")
        assert len(result["grid"]) == 3
        assert len(result["row_categories"]) == 3
        assert len(result["col_categories"]) == 3
        assert set(result["player_symbols"]) == {"p1", "p2"}
        assert result["turn_deadline"] is not None
        assert result["current_turn_player_id"] in {"p1", "p2"}
        # Room state should reflect the game being in progress.
        assert room.game_state.phase == GamePhase.GUESSING
        assert room.game_state.grid is not None
        assert room.game_state.row_categories is not None

    def test_start_grid_game_rejects_non_host(self) -> None:
        room = Room(
            code="GRID99",
            sport=Sport.NBA,
            mode=GameMode.NBA_GRID,
            host_id="p1",
            game_state=GameState(phase=GamePhase.WAITING_FOR_PLAYERS),
        )
        room.players = [
            GamePlayer(id="p1", name="Alice"),
            GamePlayer(id="p2", name="Bob"),
        ]
        gm = GameManager()
        result = gm.start_grid_game(room, "p2")
        assert not result["success"]
        assert "host" in result["error"].lower()

    def test_submit_guess_against_real_categories(self, seeded_engine) -> None:
        """Play one round: start game, submit a player that exists in the
        actual intersection. Should succeed even though we don't know which
        categories the generator picked."""
        room = Room(
            code="GRIDSG",
            sport=Sport.NBA,
            mode=GameMode.NBA_GRID,
            host_id="p1",
            game_state=GameState(phase=GamePhase.WAITING_FOR_PLAYERS),
        )
        room.players = [
            GamePlayer(id="p1", name="Alice"),
            GamePlayer(id="p2", name="Bob"),
        ]
        gm = GameManager()
        start = gm.start_grid_game(room, "p1")
        assert start["success"]

        # Pick cell (0, 0) and find a valid player for it from the categories.
        gs = room.game_state
        row = gs.row_categories[0]
        col = gs.col_categories[0]
        intersection = set(row.valid_player_ids).intersection(col.valid_player_ids)
        assert intersection, "cell has empty intersection — generator failed balance"

        # Resolve one player's name via the seeded DB.
        _, SessionLocal = seeded_engine
        session = SessionLocal()
        try:
            sample_player = session.query(Player).filter(Player.id.in_(list(intersection))).first()
        finally:
            session.close()
        assert sample_player is not None

        current = gs.current_turn_player_id
        result = gm.submit_grid_guess(room, current, 0, 0, sample_player.name)
        assert result["success"]
        assert result["correct"] is True
        assert result["player_name"] == sample_player.name
        assert gs.grid[0][0].marked_by == current
