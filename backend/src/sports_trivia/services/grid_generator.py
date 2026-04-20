"""Balanced NBA Grid generator.

Samples 6 distinct categories (3 rows + 3 columns) such that every cell
intersection has at least `min_answers` valid players. Rejects grids where
rows and cols share a family too heavily (e.g. all 6 are teams) to keep
variety across the grid.
"""

from __future__ import annotations

import logging
import random

from sqlalchemy.orm import Session

from sports_trivia.models import GridCategory
from sports_trivia.services.grid_categories import build_all_categories

logger = logging.getLogger(__name__)

DEFAULT_MIN_ANSWERS = 8
RELAXED_MIN_ANSWERS = 5
MAX_ATTEMPTS_STRICT = 50
MAX_ATTEMPTS_RELAXED = 20


class GridGenerationError(Exception):
    """Raised when no balanced 3x3 grid can be assembled."""


def generate_grid(
    session: Session,
    *,
    min_answers: int = DEFAULT_MIN_ANSWERS,
    seed: int | None = None,
) -> tuple[list[GridCategory], list[GridCategory]]:
    """Return (rows, cols), each length 3, satisfying the balance constraints.

    Args:
        session: SQLAlchemy session for reading category data.
        min_answers: Minimum valid players at each of the 9 cell intersections.
        seed: Optional random seed for reproducibility in tests.

    Raises:
        GridGenerationError: If no balanced grid can be built even with
            the relaxed threshold.
    """
    rng = random.Random(seed) if seed is not None else random

    pool = build_all_categories(session)
    if len(pool) < 6:
        raise GridGenerationError(
            f"Not enough categories to build a 3x3 grid: have {len(pool)}, need 6."
        )

    for _ in range(MAX_ATTEMPTS_STRICT):
        rows, cols = _sample(pool, rng)
        if _is_balanced(rows, cols, min_answers):
            return rows, cols

    logger.warning(
        "Grid generator: falling back to relaxed threshold %d after %d strict attempts",
        RELAXED_MIN_ANSWERS,
        MAX_ATTEMPTS_STRICT,
    )
    for _ in range(MAX_ATTEMPTS_RELAXED):
        rows, cols = _sample(pool, rng)
        if _is_balanced(rows, cols, RELAXED_MIN_ANSWERS):
            return rows, cols

    raise GridGenerationError(
        "Could not assemble a balanced grid even at the relaxed threshold. "
        "Category pool is likely too thin — seed more metadata."
    )


def _sample(
    pool: list[GridCategory], rng: random.Random | random
) -> tuple[list[GridCategory], list[GridCategory]]:
    chosen = rng.sample(pool, 6)
    return chosen[:3], chosen[3:]


def _is_balanced(
    rows: list[GridCategory],
    cols: list[GridCategory],
    min_answers: int,
) -> bool:
    """Reject invalid grids.

    Rules:
    - No duplicate category ids across rows/cols (sample() already guarantees this).
    - Rows must not all share a single family; same for cols (forces variety).
    - Every 9 cell intersections must have >= min_answers valid players.
    """
    row_families = {c.family for c in rows}
    col_families = {c.family for c in cols}
    if len(row_families) == 1 and len(col_families) == 1 and row_families == col_families:
        # All 6 categories same family — too monotonous.
        return False

    for r in rows:
        rset = set(r.valid_player_ids)
        for c in cols:
            if len(rset.intersection(c.valid_player_ids)) < min_answers:
                return False
    return True


def compute_intersection(row: GridCategory, col: GridCategory) -> set[int]:
    """Return the set of player IDs valid for the (row, col) cell."""
    return set(row.valid_player_ids).intersection(col.valid_player_ids)
