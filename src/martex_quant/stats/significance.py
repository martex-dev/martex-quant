"""Per-test significance decisions and the per-period Sharpe helper.

Consolidated from the research scripts. Two things matter here, and both are
preserved rather than unified.

**One-sided vs two-sided.** The corpus contains BOTH, and the difference is a
pre-registration decision, not an accident:

    lo > 0              one-sided — 6 sites (H08 primary, H11, H14 bar1,
                        H16, H22 bar1, H23)
    lo > 0 or hi < 0    two-sided — 10 sites (H09b/c, H13, H15-H21, H24-H32,
                        H33-H40, H44-H50, H52-H57)

A two-sided hypothesis that fired on the *opposite* side is how the ledger's
most important meta-finding was discovered — H44/H45 came back INVERTED, and
a one-sided test would have recorded them as mere failures. Collapsing these
into one function would erase that.

**No multiplicity correction is applied here.** Every historical verdict in
the ledger rests on a raw per-test 95% CI. That is a property of the
historical corpus, recorded in docs/research/mi-layer2-design.md; correcting
it retroactively would change published verdicts and requires its own
pre-registration. New work routes through ``stats.multiple_testing``.
"""

from __future__ import annotations

import polars as pl


def ci_above_zero(low: float) -> bool:
    """One-sided: the effect is positive with 95% confidence.

    Use when the pre-registered claim had a DIRECTION — "does this earn
    more", not "does this differ".
    """
    return low > 0.0


def ci_excludes_zero(low: float, high: float) -> bool:
    """Two-sided: an effect was detected, in EITHER direction.

    The direction must then be read off the point estimate and recorded. Four
    of the ledger's most informative results were two-sided tests that fired
    against their stated expectation.
    """
    return low > 0.0 or high < 0.0


def per_period_sharpe(equity: pl.Series) -> float:
    """Mean/std of an equity curve's returns, NOT annualised.

    The per-period convention is what ``probabilistic_sharpe_ratio`` and
    ``expected_max_sharpe`` expect; every one of the 9 historical DSR sites
    feeds them a per-period value. Returns 0.0 on a degenerate series rather
    than raising — the historical behaviour, byte-identical in both copies
    this replaces (phase3_studies, tsmom_study).
    """
    returns = equity.pct_change().drop_nulls()
    mean, std = returns.mean(), returns.std()
    if not isinstance(mean, float) or not isinstance(std, float) or std == 0.0:
        return 0.0
    return mean / std
