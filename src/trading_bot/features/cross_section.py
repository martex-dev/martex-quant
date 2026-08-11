"""Cross-sectional ranking spreads — the rotation family's core measurement.

Consolidates the per-day "rank the universe, buy the top k, sell the bottom
k, measure the forward spread" loop that h15_21 (H16) and h24_32 (H24-H32)
each carried a copy of. The loop bodies were byte-identical; what differed
was where nulls were dropped and whether a gate was applied.

Deliberately NOT consolidated (see docs/research/mi-layer1-panel-audit.md):

* ``h11_rotation_killtest`` builds the same measurement from Python lists of
  closes rather than a polars panel, with its own ``MIN_LISTED`` gate. A
  different data structure, not a different parameterisation.
* ``h33_40``'s H37/H38 compute the spread inside a per-day loop that also
  derives breadth, dispersion and pick-correlation. Extracting it would
  change that loop's iteration, which is exactly what this layer must not do.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl


def ranking_spread_series(
    panel: pl.DataFrame,
    rank_column: str,
    *,
    outcome_column: str,
    k: int,
    min_symbols: int,
    gate: pl.Expr | None = None,
    drop_nulls_on: Sequence[str] | None = None,
) -> list[float]:
    """One top-k-minus-bottom-k outcome spread per day.

    Days with fewer than ``min_symbols`` listed names are skipped entirely —
    a thin cross-section makes the extremes meaningless — and a day whose top
    or bottom slice averages to null contributes nothing. Both rules are
    historical and both change the resulting sample size, so they are
    explicit rather than assumed.

    ``drop_nulls_on`` reproduces the placement difference between the two
    historical callers: h24_32 dropped ``(rank_column, outcome_column)``
    INSIDE the helper, h15_21 dropped at its call site and passes ``None``.
    Dropping earlier can remove whole days, which changes the day-block
    bootstrap that consumes this series — not just the row count.

    Returns the raw per-day spreads; the caller chooses its own CI estimator
    (both historical callers used the unweighted ``daily_mean_ci``).
    """
    frame = panel.drop_nulls(list(drop_nulls_on)) if drop_nulls_on is not None else panel
    if gate is not None:
        frame = frame.filter(gate)

    spreads: list[float] = []
    for _, group in frame.group_by("day", maintain_order=True):
        if group.height < min_symbols:
            continue
        ordered = group.sort(rank_column)
        bottom = ordered.head(k)[outcome_column].mean()
        top = ordered.tail(k)[outcome_column].mean()
        if top is None or bottom is None:
            continue
        # Series.mean() is typed as a wide scalar union; on a Float64 outcome
        # column it is float or None. Narrowed rather than cast so the
        # arithmetic below stays exactly the historical `top - bot`.
        assert isinstance(top, float) and isinstance(bottom, float)
        spreads.append(top - bottom)
    return spreads
