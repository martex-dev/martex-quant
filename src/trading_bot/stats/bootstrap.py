"""Moving-block bootstrap estimators — one per historical shape.

Consolidates 16 near-duplicate definitions spread across 11 research
scripts. The audit (docs/research/mi-layer1-consolidation-plan.md §1.1)
found FOUR genuinely distinct estimators hiding behind similar names. They
are kept as four functions on purpose: merging them would silently change
published numbers.

The four shapes
---------------
``two_group_diff_ci``   mean(a) - mean(b), observation-weighted, over
                        per-day aggregated sums and counts.
``daily_mean_ci``       mean of a per-day series, UNWEIGHTED — every draw
                        contributes exactly ``block`` to the denominator.
``event_mean_ci``       mean of pooled events, COUNT-WEIGHTED — every draw
                        contributes the events it actually holds.
``flag_split_ci``       mean(flagged) - mean(unflagged), rebuilt from raw
                        observations per draw.

``daily_mean_ci`` and ``event_mean_ci`` are the dangerous pair. Both are
"a bootstrapped mean"; they differ in one line of the historical code::

    cnt += block               # daily_mean_ci  — unweighted
    cnt += pn[e] - pn[s]       # event_mean_ci  — count-weighted

On a panel with a varying number of events per day these give different
POINT ESTIMATES, not merely different intervals. That is why they are two
functions with two names rather than one function with a flag.

The RNG contract is part of the result
--------------------------------------
Every published confidence interval is a deterministic function of
``random.Random(seed)`` and the exact sequence of ``randint`` calls. This
module therefore preserves, and must keep preserving:

* ``random.Random`` — never NumPy, never ``random`` module-level state
* ``n_blocks = n // block + 1`` — note the resample is up to ``block`` days
  LONGER than the original series; that is historical, not a bug
* exactly one ``randint`` per block per bootstrap iteration, drawn in that
  nesting order
* conditional appends — samples are only recorded when the denominators are
  positive, so the list length varies and the percentile INDEX
  ``int(0.025 * len(samples))`` moves with it

Do not vectorise, pre-generate indices, reorder, or otherwise "optimise"
any of that. It would change every published CI while looking like a pure
refactor.

Parameters exist to preserve history, not to offer choice
---------------------------------------------------------
``accumulation``, ``short_series``, ``empty_denominator`` and ``nan_below``
each encode a real difference between historical call sites. Every caller
passes the value its script used. None of them is a "better" setting; see
the per-parameter docstrings for which script used which.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Sequence
from typing import Literal, NamedTuple

# How a bootstrap draw accumulates its block.
#
# "prefix_delta"  ps[e] - ps[s] over a prefix-sum array (most scripts)
# "slice_sum"     sum(values[s:e]) directly (h22_h23, and h13_h14's inline
#                 H14 bootstrap)
#
# The two differ only in floating-point summation ORDER — prefix deltas
# accumulate from index 0, slice sums from the block start. Preserved
# because the CI bound is selected by integer index into a sorted list, so
# a last-bit difference could in principle reorder adjacent draws.
Accumulation = Literal["prefix_delta", "slice_sum"]

# Upper bound handed to randint for the block start.
#
# "error"  randint(0, n - block)          — raises ValueError if n < block
# "clamp"  randint(0, max(n - block, 0))  — h44_50, h52_55_57, h53
#
# Identical whenever n >= block, which holds for every historical dataset.
#
# NOTE (found during Step 1, recorded not fixed): "clamp" LOOKS like a
# short-series guard but is not. A clamped start of 0 still indexes
# ``0 + block`` past the end of the prefix array, so n < block raises
# IndexError instead of ValueError. Neither mode supports n < block.
# Correction candidate; changing it is out of Layer 1's scope.
ShortSeries = Literal["error", "clamp"]

# Denominator handling for the POINT estimate of two_group_diff_ci.
#
# "guard"   pa[n] / max(pan[n], 1.0)  — every script except h08
# "divide"  pa[n] / pan[n]            — h08_funding_killtest only
#
# Identical on real data (counts are positive). "divide" raises
# ZeroDivisionError on an empty group where "guard" returns 0.0.
EmptyDenominator = Literal["guard", "divide"]


class CI(NamedTuple):
    """Point estimate with a 95% block-bootstrap interval.

    ``n`` is the observation count the point estimate averaged over — the
    "a" group for a two-group difference, the event count for a pooled
    event mean. Historical call sites that printed an n printed this one.
    """

    point: float
    low: float
    high: float
    n: int


def _prefix(xs: Sequence[float]) -> list[float]:
    out = [0.0]
    for x in xs:
        out.append(out[-1] + float(x))
    return out


def _block_start_bound(n: int, block: int, short_series: ShortSeries) -> int:
    if short_series == "clamp":
        return max(n - block, 0)
    return n - block


def _bounds(samples: list[float]) -> tuple[float, float]:
    """The historical percentile rule: integer index into the sorted draws.

    Deliberately NOT an interpolated quantile. ``len(samples)`` depends on
    how many draws were rejected by the caller's positivity guard, so the
    index is part of the estimator.
    """
    samples.sort()
    return samples[int(0.025 * len(samples))], samples[int(0.975 * len(samples))]


def two_group_diff_ci(
    a_sum: Sequence[float],
    a_n: Sequence[float],
    b_sum: Sequence[float],
    b_n: Sequence[float],
    *,
    block: int,
    seed: int,
    n_boot: int,
    empty_denominator: EmptyDenominator,
    short_series: ShortSeries,
) -> CI:
    """mean(a) - mean(b), observation-weighted, block-bootstrapped by day.

    Inputs are PER-DAY aggregates, already grouped and sorted by the
    caller: parallel sequences of group sums and group counts. Aggregation
    stays at the call site because null handling and drop placement differ
    per script and are themselves part of each result.

    Blocks are contiguous date ranges with the cross-section kept intact —
    symbols are correlated, so resampling symbol-days independently would
    fake precision.

    Historical callers: h08 (as pooled_diff_ci, empty_denominator="divide"),
    h09 (bootstrap_diff), h10 (pooled_diff_ci), h13_h14 (diff_ci),
    h15_21 (diff_ci), h22_h23 (day_diff_ci, block=30), h33_40 (diff_ci),
    h44_50 (diff_ci, short_series="clamp").
    """
    pa, pan, pb, pbn = (_prefix(x) for x in (a_sum, a_n, b_sum, b_n))
    n = len(a_sum)
    if empty_denominator == "guard":
        point = pa[n] / max(pan[n], 1.0) - pb[n] / max(pbn[n], 1.0)
    else:
        point = pa[n] / pan[n] - pb[n] / pbn[n]

    rng = random.Random(seed)
    n_blocks = n // block + 1
    bound = _block_start_bound(n, block, short_series)
    diffs: list[float] = []
    for _ in range(n_boot):
        sa = na = sb = nb = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, bound)
            e = s + block
            sa += pa[e] - pa[s]
            na += pan[e] - pan[s]
            sb += pb[e] - pb[s]
            nb += pbn[e] - pbn[s]
        if na > 0 and nb > 0:
            diffs.append(sa / na - sb / nb)
    low, high = _bounds(diffs)
    return CI(point, low, high, int(pan[n]))


def daily_mean_ci(
    values: Sequence[float],
    *,
    block: int,
    seed: int,
    n_boot: int,
    accumulation: Accumulation,
    short_series: ShortSeries,
    nan_below: int | None = None,
) -> CI:
    """UNWEIGHTED mean of a per-day series.

    Each bootstrap draw adds exactly ``block`` to the denominator,
    regardless of what the days contain. Use this when ``values`` holds one
    number per day — a daily cross-sectional spread, a daily portfolio
    return. For pooled events with a varying count per day use
    ``event_mean_ci`` instead: the two disagree on the point estimate.

    ``nan_below``: return NaN bounds (keeping the point estimate) when
    ``len(values) <= nan_below``. h22_h23 used ``block * 2``; the other
    callers had no such guard and pass None.

    Historical callers: h11 (bootstrap_mean), h15_21 (mean_ci),
    h24_32 (mean_ci), h22_h23 (block_mean_ci, accumulation="slice_sum",
    block=10, nan_below=20).
    """
    n = len(values)
    prefix = _prefix(values) if accumulation == "prefix_delta" else []
    point = prefix[n] / n if accumulation == "prefix_delta" else sum(values) / n
    if nan_below is not None and n <= nan_below:
        return CI(point, float("nan"), float("nan"), n)

    rng = random.Random(seed)
    n_blocks = n // block + 1
    bound = _block_start_bound(n, block, short_series)
    means: list[float] = []
    for _ in range(n_boot):
        total = 0.0
        cnt = 0
        for _ in range(n_blocks):
            s = rng.randint(0, bound)
            if accumulation == "prefix_delta":
                total += prefix[s + block] - prefix[s]
            else:
                total += sum(values[s : s + block])
            cnt += block
        means.append(total / cnt)
    low, high = _bounds(means)
    return CI(point, low, high, n)


def event_mean_ci(
    v_sum: Sequence[float],
    v_n: Sequence[float],
    *,
    block: int,
    seed: int,
    n_boot: int,
    accumulation: Accumulation,
    short_series: ShortSeries,
    nan_below: int | None = None,
) -> CI:
    """COUNT-WEIGHTED mean of events pooled by day.

    Each bootstrap draw adds the number of events its block actually holds,
    so days with more events weigh more — the opposite convention to
    ``daily_mean_ci``. Inputs are per-day event sums and per-day event
    counts, aggregated and sorted by the caller.

    Historical callers: h33_40 (event_mean_ci), h44_50, h52_55_57 and h53
    (event_mean_ci, short_series="clamp"), h13_h14's inline H14 bootstrap
    (accumulation="slice_sum", nan_below=block).
    """
    n = len(v_sum)
    if accumulation == "prefix_delta":
        ps, pn = _prefix(v_sum), _prefix(v_n)
        total_n = pn[n]
        point = ps[n] / max(total_n, 1.0)
    else:
        ps, pn = [], []
        total_n = float(sum(v_n))
        point = sum(v_sum) / max(total_n, 1.0)
    if nan_below is not None and n <= nan_below:
        return CI(point, float("nan"), float("nan"), int(total_n))

    rng = random.Random(seed)
    n_blocks = n // block + 1
    bound = _block_start_bound(n, block, short_series)
    means: list[float] = []
    for _ in range(n_boot):
        total = cnt = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, bound)
            e = s + block
            if accumulation == "prefix_delta":
                total += ps[e] - ps[s]
                cnt += pn[e] - pn[s]
            else:
                total += sum(v_sum[s:e])
                cnt += sum(v_n[s:e])
        if cnt > 0:
            means.append(total / cnt)
    low, high = _bounds(means)
    return CI(point, low, high, int(total_n))


def flag_split_ci(
    values: Sequence[float],
    flags: Sequence[bool],
    *,
    block: int,
    seed: int,
    n_boot: int,
) -> CI:
    """mean(values[flags]) - mean(values[~flags]), rebuilt per draw.

    Structurally different from ``two_group_diff_ci``: instead of
    accumulating pre-aggregated sums and counts, each draw re-partitions the
    raw observations of its blocks into two lists and averages them with
    ``statistics.fmean``. Kept separate because the float path and the
    membership handling are both part of the published result.

    Historical caller: v2_m1_killtest (block_bootstrap_ci, block=60 — the
    only 60-day block in the corpus, chosen to cover a 30-day horizon's
    autocorrelation).
    """
    n = len(values)
    rng = random.Random(seed)
    n_blocks = (n // block) + 1
    diffs: list[float] = []
    for _ in range(n_boot):
        rising: list[float] = []
        falling: list[float] = []
        for _ in range(n_blocks):
            start = rng.randint(0, n - block)
            for i in range(start, start + block):
                (rising if flags[i] else falling).append(values[i])
        if rising and falling:
            diffs.append(statistics.fmean(rising) - statistics.fmean(falling))
    diffs.sort()
    flagged = [v for v, f in zip(values, flags, strict=True) if f]
    unflagged = [v for v, f in zip(values, flags, strict=True) if not f]
    point = statistics.fmean(flagged) - statistics.fmean(unflagged)
    return CI(point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))], sum(flags))
