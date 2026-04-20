"""Tests for NBA Grid game-manager methods.

These tests exercise the grid state machine by seeding `GameState` directly,
bypassing `start_grid_game` (which hits the DB). `submit_grid_guess` needs a
real Player table for name resolution — we spin up an in-memory SQLite DB and
monkey-patch `get_session` in the manager.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from sports_trivia.db.models import Base, Player
from sports_trivia.models import (
    GameMode,
    GamePhase,
    GameState,
    GridCategory,
    GridCell,
    Room,
    Sport,
)
from sports_trivia.models import (
    Player as GamePlayer,
)
from sports_trivia.services.game_manager import (
    GRID_DRAW_COOLDOWN_SECONDS,
    GRID_TURN_SECONDS,
    GameManager,
)

# ---------- fixtures ----------


@pytest.fixture
def gm() -> GameManager:
    return GameManager()


@pytest.fixture
def db_players() -> list[tuple[int, str, str]]:
    """Synthetic (id, name, external_id) triples used for name lookup."""
    return [
        (1, "LeBron James", "2544"),
        (2, "Kobe Bryant", "977"),
        (3, "Shaquille O'Neal", "406"),
        (4, "Magic Johnson", "77142"),
        (5, "Michael Jordan", "893"),
        (6, "Stephen Curry", "201939"),
    ]


@pytest.fixture
def mem_session(
    db_players: list[tuple[int, str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> Session:
    """In-memory SQLite session seeded with the synthetic players. Also
    patches `get_session` inside the game_manager module so grid methods
    query this session.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    for pid, name, ext_id in db_players:
        session.add(
            Player(
                id=pid,
                name=name,
                name_normalized=name.lower(),
                external_id=ext_id,
            )
        )
    session.commit()

    def _factory() -> Session:
        # Return a fresh session each call; tests don't write, so safe.
        return SessionLocal()

    import sports_trivia.db as db_pkg

    monkeypatch.setattr(db_pkg, "get_session", _factory)
    return session


def _make_category(cid: str, family: str, name: str, ids: list[int]) -> GridCategory:
    return GridCategory(
        id=cid,
        family=family,
        display_name=name,
        valid_player_ids=ids,
    )


def _make_grid_room(
    rows: list[GridCategory],
    cols: list[GridCategory],
    current_turn: str = "p1",
) -> Room:
    """Construct a room already in an active grid game."""
    room = Room(
        code="GRID01",
        sport=Sport.NBA,
        mode=GameMode.NBA_GRID,
        host_id="p1",
        game_state=GameState(),
    )
    room.players = [
        GamePlayer(id="p1", name="Alice"),
        GamePlayer(id="p2", name="Bob"),
    ]
    gs = room.game_state
    gs.phase = GamePhase.GUESSING
    gs.grid = [[GridCell() for _ in range(3)] for _ in range(3)]
    gs.row_categories = rows
    gs.col_categories = cols
    gs.player_symbols = {"p1": "X", "p2": "O"}
    gs.turn_deadline = time.time() + GRID_TURN_SECONDS
    gs.current_turn_player_id = current_turn
    return room


# ---------- per-turn timer ----------


class TestTurnTimer:
    def test_swap_grants_fresh_60s(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")
        # Pretend only 5s left on p1's turn.
        room.game_state.turn_deadline = time.time() + 5.0

        gm._grid_swap_turn(room)

        # Opponent gets a full fresh budget.
        remaining = room.game_state.turn_deadline - time.time()
        assert 59.0 <= remaining <= 60.5

    def test_timer_expiry_auto_skips(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")

        res = gm.grid_timer_expired(room, "p1")

        assert res["success"]
        assert res["reason"] == "timeout"
        # Game continues — no end-game signal.
        assert res.get("game_ended") is None
        assert room.game_state.phase == GamePhase.GUESSING
        assert room.game_state.current_turn_player_id == "p2"

    def test_stale_timer_expiry_is_noop(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")
        gm._grid_swap_turn(room)  # turn already advanced

        res = gm.grid_timer_expired(room, "p1")
        assert not res["success"]


class TestSwapTurn:
    def test_hands_turn_to_opponent(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")

        gm._grid_swap_turn(room)
        assert room.game_state.current_turn_player_id == "p2"
        gm._grid_swap_turn(room)
        assert room.game_state.current_turn_player_id == "p1"


# ---------- win detection ----------


class TestWinDetection:
    def test_detects_row_three_in_row(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        grid = room.game_state.grid
        for c in range(3):
            grid[0][c].marked_by = "p1"
            grid[0][c].symbol = "X"
        assert gm._grid_check_winner(room) == "p1"

    def test_detects_column_three_in_row(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        grid = room.game_state.grid
        for r in range(3):
            grid[r][1].marked_by = "p2"
        assert gm._grid_check_winner(room) == "p2"

    def test_detects_main_diagonal(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        grid = room.game_state.grid
        for i in range(3):
            grid[i][i].marked_by = "p1"
        assert gm._grid_check_winner(room) == "p1"

    def test_detects_anti_diagonal(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        grid = room.game_state.grid
        grid[0][2].marked_by = "p2"
        grid[1][1].marked_by = "p2"
        grid[2][0].marked_by = "p2"
        assert gm._grid_check_winner(room) == "p2"

    def test_no_winner_mixed_line(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        grid = room.game_state.grid
        grid[0][0].marked_by = "p1"
        grid[0][1].marked_by = "p2"
        grid[0][2].marked_by = "p1"
        assert gm._grid_check_winner(room) is None


# ---------- board full ----------


class TestBoardFull:
    def test_true_when_all_cells_marked(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        for r in range(3):
            for c in range(3):
                room.game_state.grid[r][c].marked_by = "p1" if (r + c) % 2 == 0 else "p2"
        assert gm._grid_board_full(room) is True

    def test_false_when_empty_cell_remains(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        room.game_state.grid[0][0].marked_by = "p1"
        assert gm._grid_board_full(room) is False


# ---------- skip ----------


class TestSkipTurn:
    def test_skip_passes_turn(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")

        res = gm.skip_grid_turn(room, "p1")
        assert res["success"]
        assert res["reason"] == "skip"
        assert res["next_turn"] == "p2"
        assert room.game_state.current_turn_player_id == "p2"

    def test_skip_rejected_when_not_your_turn(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")
        res = gm.skip_grid_turn(room, "p2")
        assert not res["success"]
        assert "turn" in res["error"].lower()

    def test_skip_grants_fresh_timer_to_opponent(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")
        # Only 3s left on p1's turn.
        room.game_state.turn_deadline = time.time() + 3.0

        res = gm.skip_grid_turn(room, "p1")

        assert res["success"]
        assert res["next_turn"] == "p2"
        remaining = room.game_state.turn_deadline - time.time()
        assert 59.0 <= remaining <= 60.5  # opponent got a fresh 60s


# ---------- draw proposals ----------


class TestDrawProposals:
    def test_propose_stores_proposal(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)

        res = gm.propose_grid_draw(room, "p1")
        assert res["success"]
        assert res["proposer_id"] == "p1"
        assert room.game_state.draw_proposal is not None

    def test_double_propose_rejected(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        gm.propose_grid_draw(room, "p1")
        res = gm.propose_grid_draw(room, "p2")
        assert not res["success"]

    def test_self_response_rejected(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        gm.propose_grid_draw(room, "p1")
        res = gm.respond_grid_draw(room, "p1", accept=True)
        assert not res["success"]

    def test_accept_ends_game_as_draw(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        gm.propose_grid_draw(room, "p1")
        res = gm.respond_grid_draw(room, "p2", accept=True)
        assert res["success"]
        assert res["ended"] is True
        assert res["end_reason"] == "draw_accepted"
        assert res["winner_id"] is None
        assert room.game_state.phase == GamePhase.ROUND_END

    def test_decline_clears_proposal_and_sets_cooldown(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        gm.propose_grid_draw(room, "p1")
        res = gm.respond_grid_draw(room, "p2", accept=False)
        assert res["success"]
        assert res["ended"] is False
        assert room.game_state.draw_proposal is None
        assert room.game_state.last_draw_decline_at is not None

    def test_cooldown_blocks_repropose(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        room.game_state.last_draw_decline_at = time.time() - 1.0  # 1s ago

        res = gm.propose_grid_draw(room, "p1")
        assert not res["success"]
        assert "cooldown" in res["error"].lower()

    def test_cooldown_expires(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols)
        room.game_state.last_draw_decline_at = time.time() - GRID_DRAW_COOLDOWN_SECONDS - 1.0
        res = gm.propose_grid_draw(room, "p1")
        assert res["success"]


# ---------- submit_grid_guess (requires DB) ----------


@pytest.mark.usefixtures("mem_session")
class TestSubmitGridGuess:
    def test_correct_guess_marks_cell(self, gm: GameManager) -> None:
        rows = [
            _make_category("r0", "team", "Lakers", [1, 2, 3]),
            _make_category("r1", "team", "Bulls", [5]),
            _make_category("r2", "team", "Heat", [1, 3]),
        ]
        cols = [
            _make_category("c0", "award", "MVP", [1, 2, 3, 5]),
            _make_category("c1", "award", "FMVP", [1, 2, 3, 5]),
            _make_category("c2", "award", "DPOY", [3, 5]),
        ]
        room = _make_grid_room(rows, cols, current_turn="p1")

        res = gm.submit_grid_guess(room, "p1", 0, 0, "LeBron James")
        assert res["success"]
        assert res["correct"]
        assert res["player_name"] == "LeBron James"
        assert res["symbol"] == "X"
        assert room.game_state.grid[0][0].marked_by == "p1"
        assert room.game_state.grid[0][0].player_name == "LeBron James"
        assert room.game_state.grid[0][0].player_image_url is not None

    def test_wrong_guess_passes_turn(self, gm: GameManager) -> None:
        rows = [
            _make_category("r0", "team", "Lakers", [1, 2, 3]),
            _make_category("r1", "team", "Bulls", [5]),
            _make_category("r2", "team", "Heat", [1, 3]),
        ]
        cols = [
            _make_category("c0", "award", "MVP", [1, 2, 3, 5]),
            _make_category("c1", "award", "FMVP", [1, 2, 3, 5]),
            _make_category("c2", "award", "DPOY", [3, 5]),
        ]
        room = _make_grid_room(rows, cols, current_turn="p1")

        res = gm.submit_grid_guess(room, "p1", 0, 0, "Michael Jordan")  # MJ not in r0 ∩ c0
        assert res["success"]
        assert res["correct"] is False
        assert res["next_turn"] == "p2"
        assert room.game_state.grid[0][0].marked_by is None

    def test_not_your_turn(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")
        res = gm.submit_grid_guess(room, "p2", 0, 0, "LeBron James")
        assert not res["success"]

    def test_cell_already_marked(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")
        room.game_state.grid[0][0].marked_by = "p2"
        res = gm.submit_grid_guess(room, "p1", 0, 0, "LeBron James")
        assert not res["success"]

    def test_three_in_a_row_ends_game(self, gm: GameManager) -> None:
        rows = [_make_category(f"r{i}", "team", f"R{i}", [1, 2, 3]) for i in range(3)]
        cols = [_make_category(f"c{i}", "award", f"C{i}", [1, 2, 3]) for i in range(3)]
        room = _make_grid_room(rows, cols, current_turn="p1")
        # Pre-mark the first two cells of row 0 by p1
        room.game_state.grid[0][0].marked_by = "p1"
        room.game_state.grid[0][0].symbol = "X"
        room.game_state.grid[0][1].marked_by = "p1"
        room.game_state.grid[0][1].symbol = "X"

        res = gm.submit_grid_guess(room, "p1", 0, 2, "LeBron James")
        assert res["success"]
        assert res["correct"]
        assert res.get("game_ended") is True
        assert res["end_reason"] == "three_in_row"
        assert res["winner_id"] == "p1"
        assert room.game_state.phase == GamePhase.ROUND_END
        # Score awarded
        assert room.get_player("p1").score == 1
