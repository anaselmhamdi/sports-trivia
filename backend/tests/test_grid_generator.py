"""Tests for the NBA Grid generator.

The generator samples 6 categories (3 rows + 3 cols) such that every cell has
>= min_answers valid players, and families don't all collapse to one type.
"""

from __future__ import annotations

import pytest

from sports_trivia.models import GridCategory
from sports_trivia.services import grid_generator
from sports_trivia.services.grid_generator import (
    GridGenerationError,
    _is_balanced,
    compute_intersection,
    generate_grid,
)


def _cat(cid: str, family: str, ids: list[int]) -> GridCategory:
    return GridCategory(
        id=cid,
        family=family,
        display_name=cid,
        valid_player_ids=ids,
    )


class TestIsBalanced:
    def test_accepts_well_balanced(self) -> None:
        """Every cell has >= min_answers valid players."""
        rows = [
            _cat("a", "team", list(range(0, 50))),
            _cat("b", "team", list(range(10, 60))),
            _cat("c", "team", list(range(20, 70))),
        ]
        cols = [
            _cat("d", "award", list(range(0, 50))),
            _cat("e", "award", list(range(10, 60))),
            _cat("f", "award", list(range(20, 70))),
        ]
        assert _is_balanced(rows, cols, min_answers=8)

    def test_rejects_sparse_cell(self) -> None:
        """Even one cell below the threshold rejects the grid."""
        rows = [
            _cat("a", "team", [1, 2, 3]),
            _cat("b", "team", list(range(0, 50))),
            _cat("c", "team", list(range(0, 50))),
        ]
        cols = [
            _cat("d", "award", list(range(10, 60))),
            _cat("e", "award", list(range(10, 60))),
            _cat("f", "award", list(range(10, 60))),
        ]
        assert not _is_balanced(rows, cols, min_answers=8)

    def test_rejects_all_same_family(self) -> None:
        """All 6 categories sharing the same family is too monotonous."""
        rows = [
            _cat("a", "team", list(range(0, 100))),
            _cat("b", "team", list(range(0, 100))),
            _cat("c", "team", list(range(0, 100))),
        ]
        cols = [
            _cat("d", "team", list(range(0, 100))),
            _cat("e", "team", list(range(0, 100))),
            _cat("f", "team", list(range(0, 100))),
        ]
        assert not _is_balanced(rows, cols, min_answers=8)

    def test_accepts_mixed_families(self) -> None:
        """Different families on rows and cols is fine."""
        rows = [
            _cat("a", "team", list(range(0, 100))),
            _cat("b", "team", list(range(0, 100))),
            _cat("c", "team", list(range(0, 100))),
        ]
        cols = [
            _cat("d", "award", list(range(0, 100))),
            _cat("e", "decade", list(range(0, 100))),
            _cat("f", "stat", list(range(0, 100))),
        ]
        assert _is_balanced(rows, cols, min_answers=8)


class TestComputeIntersection:
    def test_empty_when_disjoint(self) -> None:
        row = _cat("r", "team", [1, 2, 3])
        col = _cat("c", "team", [4, 5, 6])
        assert compute_intersection(row, col) == set()

    def test_returns_common_ids(self) -> None:
        row = _cat("r", "team", [1, 2, 3, 4])
        col = _cat("c", "award", [2, 3, 5])
        assert compute_intersection(row, col) == {2, 3}


class TestGenerateGrid:
    """Generator tests that bypass DB via monkeypatching `build_all_categories`."""

    def test_fails_with_too_few_categories(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            grid_generator,
            "build_all_categories",
            lambda _s: [_cat(f"c{i}", "team", list(range(50))) for i in range(3)],
        )
        with pytest.raises(GridGenerationError):
            generate_grid(session=None, seed=42)  # type: ignore[arg-type]

    def test_generates_balanced_grid_deterministically(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With a dense pool and fixed seed, generation succeeds and returns 3+3 cats."""
        pool = []
        # Team family — large, diverse player sets
        for i in range(8):
            pool.append(_cat(f"team_{i}", "team", list(range(i * 5, i * 5 + 80))))
        # Award family — different player IDs to avoid full overlap but ensure intersection
        for i in range(6):
            pool.append(_cat(f"award_{i}", "award", list(range(i * 3, i * 3 + 90))))

        monkeypatch.setattr(grid_generator, "build_all_categories", lambda _session: pool)

        rows, cols = generate_grid(session=None, seed=1)  # type: ignore[arg-type]
        assert len(rows) == 3
        assert len(cols) == 3
        # All 6 must be unique
        ids = {c.id for c in rows + cols}
        assert len(ids) == 6

    def test_every_cell_meets_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every cell in a generated grid has ≥ min_answers valid players."""
        pool = []
        for i in range(8):
            pool.append(_cat(f"team_{i}", "team", list(range(i * 5, i * 5 + 80))))
        for i in range(6):
            pool.append(_cat(f"award_{i}", "award", list(range(i * 3, i * 3 + 90))))

        monkeypatch.setattr(grid_generator, "build_all_categories", lambda _session: pool)

        rows, cols = generate_grid(session=None, seed=7, min_answers=8)  # type: ignore[arg-type]
        for r in rows:
            for c in cols:
                assert len(compute_intersection(r, c)) >= 8

    def test_rng_reproducible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pool = []
        for i in range(8):
            pool.append(_cat(f"team_{i}", "team", list(range(i * 5, i * 5 + 80))))
        for i in range(6):
            pool.append(_cat(f"award_{i}", "award", list(range(i * 3, i * 3 + 90))))

        monkeypatch.setattr(grid_generator, "build_all_categories", lambda _session: pool)

        r1, c1 = generate_grid(session=None, seed=99)  # type: ignore[arg-type]
        r2, c2 = generate_grid(session=None, seed=99)  # type: ignore[arg-type]
        assert [x.id for x in r1] == [x.id for x in r2]
        assert [x.id for x in c1] == [x.id for x in c2]
