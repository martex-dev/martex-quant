"""Canonical bootstrap estimators vs the historical implementations.

Each test embeds a VERBATIM copy of the code as it exists in the research
script it came from, and asserts the canonical function reproduces it
exactly. That is the unit-level proof behind the golden gate: the goldens
show published output is unchanged, these show WHY.

The historical copies are reference fixtures. They must never be "tidied" —
their float ordering, guards and RNG call structure are the specification.
"""

from __future__ import annotations

import random
import statistics
import types

import pytest

from trading_bot.stats import bootstrap
from trading_bot.stats.bootstrap import (
    daily_mean_ci,
    event_mean_ci,
    flag_split_ci,
    two_group_diff_ci,
)

N_BOOT = 200  # smaller than the scripts' 5_000; the comparison is exact either way


def _series(n: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    return [rng.gauss(0.001, 0.02) for _ in range(n)]


def _counts(n: int, seed: int) -> list[float]:
    """Varying events per day — the case that separates weighted from
    unweighted means."""
    rng = random.Random(seed)
    return [float(rng.randint(0, 4)) for _ in range(n)]


# --- verbatim historical implementations --------------------------------------------


def _hist_prefix(xs: list[float]) -> list[float]:
    out = [0.0]
    for x in xs:
        out.append(out[-1] + float(x))
    return out


def _hist_diff_ci_h15_21(
    a_sum: list[float],
    a_n: list[float],
    b_sum: list[float],
    b_n: list[float],
    seed: int,
    block: int,
    n_boot: int,
) -> tuple[float, float, float]:
    """scripts/h15_21_killtests.py::diff_ci (also h33_40, h13_h14, h22_h23)."""
    pa, pan, pb, pbn = (_hist_prefix(x) for x in (a_sum, a_n, b_sum, b_n))
    n = len(a_sum)
    point = pa[n] / max(pan[n], 1.0) - pb[n] / max(pbn[n], 1.0)
    rng = random.Random(seed)
    n_blocks = n // block + 1
    diffs = []
    for _ in range(n_boot):
        sa = na = sb = nb = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, n - block)
            e = s + block
            sa += pa[e] - pa[s]
            na += pan[e] - pan[s]
            sb += pb[e] - pb[s]
            nb += pbn[e] - pbn[s]
        if na > 0 and nb > 0:
            diffs.append(sa / na - sb / nb)
    diffs.sort()
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def _hist_pooled_diff_ci_h08(
    a_sum: list[float],
    a_n: list[float],
    b_sum: list[float],
    b_n: list[float],
    seed: int,
    block: int,
    n_boot: int,
) -> tuple[float, float, float]:
    """scripts/h08_funding_killtest.py::pooled_diff_ci — note the UNGUARDED
    point denominator, the one place it differs from h10's copy."""
    p_ls, p_ln, p_hs, p_hn = (_hist_prefix(x) for x in (a_sum, a_n, b_sum, b_n))
    n = len(a_sum)
    point = (p_ls[n] / p_ln[n]) - (p_hs[n] / p_hn[n])
    rng = random.Random(seed)
    n_blocks = n // block + 1
    diffs = []
    for _ in range(n_boot):
        ls = ln = hs = hn = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, n - block)
            e = s + block
            ls += p_ls[e] - p_ls[s]
            ln += p_ln[e] - p_ln[s]
            hs += p_hs[e] - p_hs[s]
            hn += p_hn[e] - p_hn[s]
        if ln > 0 and hn > 0:
            diffs.append(ls / ln - hs / hn)
    diffs.sort()
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def _hist_bootstrap_mean_h11(
    values: list[float], seed: int, block: int, n_boot: int
) -> tuple[float, float, float]:
    """scripts/h11_rotation_killtest.py::bootstrap_mean (also h15_21/h24_32
    mean_ci). UNWEIGHTED: count += block."""
    n = len(values)
    p = _hist_prefix(values)
    point = p[n] / n
    rng = random.Random(seed)
    n_blocks = n // block + 1
    means = []
    for _ in range(n_boot):
        total = 0.0
        count = 0
        for _ in range(n_blocks):
            s = rng.randint(0, n - block)
            total += p[s + block] - p[s]
            count += block
        means.append(total / count)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def _hist_block_mean_ci_h22(
    values: list[float], block: int, seed: int, n_boot: int
) -> tuple[float, float, float]:
    """scripts/h22_h23_studies.py::block_mean_ci — slice sums, NaN below
    block*2, configurable block (H22 uses 10)."""
    n = len(values)
    point = sum(values) / n
    if n <= block * 2:
        return point, float("nan"), float("nan")
    rng = random.Random(seed)
    n_blocks = n // block + 1
    means = []
    for _ in range(n_boot):
        total = 0.0
        cnt = 0
        for _ in range(n_blocks):
            s = rng.randint(0, n - block)
            total += sum(values[s : s + block])
            cnt += block
        means.append(total / cnt)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def _hist_event_mean_ci_h44(
    v_sum: list[float], v_n: list[float], seed: int, block: int, n_boot: int
) -> tuple[float, float, float, int]:
    """scripts/h44_50_killtests.py::event_mean_ci (also h52_55_57, h53).
    COUNT-WEIGHTED, clamped block start."""
    ps, pn = _hist_prefix(v_sum), _hist_prefix(v_n)
    n = len(v_sum)
    n_events = int(pn[n])
    point = ps[n] / max(pn[n], 1.0)
    rng = random.Random(seed)
    n_blocks = n // block + 1
    means = []
    for _ in range(n_boot):
        total = cnt = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, max(n - block, 0))
            e = s + block
            total += ps[e] - ps[s]
            cnt += pn[e] - pn[s]
        if cnt > 0:
            means.append(total / cnt)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))], n_events


def _hist_event_mean_ci_h33(
    v_sum: list[float], v_n: list[float], seed: int, block: int, n_boot: int
) -> tuple[float, float, float]:
    """scripts/h33_40_killtests.py::event_mean_ci — same estimator as h44's
    but with the UNCLAMPED block start."""
    ps, pn = _hist_prefix(v_sum), _hist_prefix(v_n)
    n = len(v_sum)
    point = ps[n] / max(pn[n], 1.0)
    rng = random.Random(seed)
    n_blocks = n // block + 1
    means = []
    for _ in range(n_boot):
        total = cnt = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, n - block)
            e = s + block
            total += ps[e] - ps[s]
            cnt += pn[e] - pn[s]
        if cnt > 0:
            means.append(total / cnt)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def _hist_h14_inline(
    sums: list[float], ns: list[float], seed: int, block: int, n_boot: int
) -> tuple[float, float, float]:
    """scripts/h13_h14_killtests.py::h14 — the inline bootstrap: count
    weighted, slice sums, NaN when n <= block."""
    n = len(sums)
    rng = random.Random(seed)
    point = sum(sums) / max(sum(ns), 1)
    boots = []
    if n > block:
        n_blocks = n // block + 1
        for _ in range(n_boot):
            ts = tn = 0.0
            for _ in range(n_blocks):
                s = rng.randint(0, n - block)
                ts += sum(sums[s : s + block])
                tn += sum(ns[s : s + block])
            if tn > 0:
                boots.append(ts / tn)
        boots.sort()
        lo1, hi1 = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))]
    else:
        lo1, hi1 = float("nan"), float("nan")
    return point, lo1, hi1


def _hist_block_bootstrap_ci_v2(
    values: list[float], flags: list[bool], n_boot: int, block: int, seed: int
) -> tuple[float, float, float]:
    """scripts/v2_m1_killtest.py::block_bootstrap_ci — raw re-partition per
    draw, statistics.fmean, 60-day blocks."""
    n = len(values)
    rng = random.Random(seed)
    diffs = []
    n_blocks = (n // block) + 1
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
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


# --- shape A: two-group difference ---------------------------------------------------


def test_two_group_diff_matches_h15_21() -> None:
    a_sum, a_n = _series(400, 1), _counts(400, 2)
    b_sum, b_n = _series(400, 3), _counts(400, 4)
    expected = _hist_diff_ci_h15_21(a_sum, a_n, b_sum, b_n, seed=151, block=30, n_boot=N_BOOT)
    actual = two_group_diff_ci(
        a_sum,
        a_n,
        b_sum,
        b_n,
        block=30,
        seed=151,
        n_boot=N_BOOT,
        empty_denominator="guard",
        short_series="error",
    )
    assert (actual.point, actual.low, actual.high) == expected


def test_two_group_diff_matches_h08_unguarded_denominator() -> None:
    a_sum, a_n = _series(400, 5), _counts(400, 6)
    b_sum, b_n = _series(400, 7), _counts(400, 8)
    expected = _hist_pooled_diff_ci_h08(a_sum, a_n, b_sum, b_n, seed=8, block=30, n_boot=N_BOOT)
    actual = two_group_diff_ci(
        a_sum,
        a_n,
        b_sum,
        b_n,
        block=30,
        seed=8,
        n_boot=N_BOOT,
        empty_denominator="divide",
        short_series="error",
    )
    assert (actual.point, actual.low, actual.high) == expected


def test_empty_denominator_modes_differ_only_in_where_they_fail() -> None:
    """h08 divides directly where every other script guards.

    Neither mode SURVIVES an entirely empty group — they fail at different
    points. "divide" raises ZeroDivisionError computing the point estimate;
    "guard" gets past that but every bootstrap draw is rejected by the
    ``na > 0 and nb > 0`` test, leaving no samples to take a percentile of.
    Recorded, not fixed: making either mode return something for degenerate
    input would be a statistical change Layer 1 is forbidden to make.
    """
    a_sum, a_n = [0.0] * 100, [0.0] * 100  # group A never populated
    b_sum, b_n = _series(100, 9), [1.0] * 100
    with pytest.raises(ZeroDivisionError):
        two_group_diff_ci(
            a_sum,
            a_n,
            b_sum,
            b_n,
            block=30,
            seed=1,
            n_boot=10,
            empty_denominator="divide",
            short_series="error",
        )
    with pytest.raises(IndexError):
        two_group_diff_ci(
            a_sum,
            a_n,
            b_sum,
            b_n,
            block=30,
            seed=1,
            n_boot=10,
            empty_denominator="guard",
            short_series="error",
        )


# --- shape B: unweighted daily mean --------------------------------------------------


def test_daily_mean_prefix_matches_h11() -> None:
    values = _series(500, 11)
    expected = _hist_bootstrap_mean_h11(values, seed=11, block=30, n_boot=N_BOOT)
    actual = daily_mean_ci(
        values,
        block=30,
        seed=11,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    assert (actual.point, actual.low, actual.high) == expected


def test_daily_mean_slice_matches_h22_with_ten_day_blocks() -> None:
    values = _series(300, 22)
    expected = _hist_block_mean_ci_h22(values, block=10, seed=22, n_boot=N_BOOT)
    actual = daily_mean_ci(
        values,
        block=10,
        seed=22,
        n_boot=N_BOOT,
        accumulation="slice_sum",
        short_series="error",
        nan_below=20,
    )
    assert (actual.point, actual.low, actual.high) == expected


def test_daily_mean_nan_below_returns_point_with_nan_bounds() -> None:
    values = _series(15, 23)
    expected = _hist_block_mean_ci_h22(values, block=10, seed=22, n_boot=N_BOOT)
    actual = daily_mean_ci(
        values,
        block=10,
        seed=22,
        n_boot=N_BOOT,
        accumulation="slice_sum",
        short_series="error",
        nan_below=20,
    )
    assert actual.point == expected[0]
    assert actual.low != actual.low and actual.high != actual.high  # NaN


# --- shape C: count-weighted event mean ----------------------------------------------


def test_event_mean_prefix_clamped_matches_h44() -> None:
    v_sum, v_n = _series(400, 44), _counts(400, 45)
    expected = _hist_event_mean_ci_h44(v_sum, v_n, seed=4410, block=30, n_boot=N_BOOT)
    actual = event_mean_ci(
        v_sum,
        v_n,
        block=30,
        seed=4410,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="clamp",
    )
    assert actual == expected


def test_event_mean_prefix_unclamped_matches_h33() -> None:
    v_sum, v_n = _series(400, 33), _counts(400, 34)
    expected = _hist_event_mean_ci_h33(v_sum, v_n, seed=3310, block=30, n_boot=N_BOOT)
    actual = event_mean_ci(
        v_sum,
        v_n,
        block=30,
        seed=3310,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    assert (actual.point, actual.low, actual.high) == expected


def test_event_mean_slice_matches_h14_inline() -> None:
    sums, ns = _series(400, 14), _counts(400, 15)
    expected = _hist_h14_inline(sums, ns, seed=14, block=30, n_boot=N_BOOT)
    actual = event_mean_ci(
        sums,
        ns,
        block=30,
        seed=14,
        n_boot=N_BOOT,
        accumulation="slice_sum",
        short_series="error",
        nan_below=30,
    )
    assert (actual.point, actual.low, actual.high) == expected


def test_weighted_and_unweighted_means_genuinely_disagree() -> None:
    """The merge this module exists to prevent.

    With a varying number of events per day, the unweighted daily mean and
    the count-weighted event mean differ in the POINT estimate, not just the
    interval.
    """
    v_sum = [10.0, 1.0, 1.0, 1.0] * 25
    v_n = [10.0, 1.0, 1.0, 1.0] * 25
    unweighted = daily_mean_ci(
        v_sum,
        block=30,
        seed=1,
        n_boot=50,
        accumulation="prefix_delta",
        short_series="error",
    )
    weighted = event_mean_ci(
        v_sum,
        v_n,
        block=30,
        seed=1,
        n_boot=50,
        accumulation="prefix_delta",
        short_series="error",
    )
    assert unweighted.point == pytest.approx(3.25)  # mean of the daily values
    assert weighted.point == pytest.approx(1.0)  # sum(v_sum) / sum(v_n)
    assert unweighted.point != weighted.point


# --- shape D: flag split -------------------------------------------------------------


def test_flag_split_matches_v2_m1_with_sixty_day_blocks() -> None:
    values = _series(500, 60)
    rng = random.Random(61)
    flags = [rng.random() > 0.5 for _ in range(500)]
    expected = _hist_block_bootstrap_ci_v2(values, flags, n_boot=N_BOOT, block=60, seed=11)
    actual = flag_split_ci(values, flags, block=60, seed=11, n_boot=N_BOOT)
    assert (actual.point, actual.low, actual.high) == expected


# --- the RNG contract ----------------------------------------------------------------


class _CountingRandom(random.Random):
    """Records every randint call so the draw budget can be asserted."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.calls: list[tuple[int, int]] = []
        self.results: list[int] = []

    def randint(self, a: int, b: int) -> int:  # type: ignore[override]
        self.calls.append((a, b))
        value: int = super().randint(a, b)
        self.results.append(value)
        return value


@pytest.fixture
def counting_rng(monkeypatch: pytest.MonkeyPatch) -> list[_CountingRandom]:
    made: list[_CountingRandom] = []

    def factory(seed: int) -> _CountingRandom:
        rng = _CountingRandom(seed)
        made.append(rng)
        return rng

    monkeypatch.setattr(bootstrap, "random", types.SimpleNamespace(Random=factory))
    return made


@pytest.mark.parametrize(
    ("n", "block"),
    [(400, 30), (400, 60), (300, 10)],  # every historical block length
)
def test_rng_draw_budget_is_exactly_n_blocks_per_iteration(
    counting_rng: list[_CountingRandom], n: int, block: int
) -> None:
    """One randint per block per bootstrap iteration — no more, no fewer.

    The draw COUNT is as load-bearing as the seed: consuming one extra draw
    shifts every subsequent block start and moves every published CI.
    """
    values = _series(n, 99)
    n_boot = 17
    daily_mean_ci(
        values,
        block=block,
        seed=5,
        n_boot=n_boot,
        accumulation="prefix_delta",
        short_series="error",
    )
    (rng,) = counting_rng
    assert len(rng.calls) == n_boot * (n // block + 1)
    assert {bounds for bounds in rng.calls} == {(0, n - block)}


def test_rng_draw_order_is_identical_across_shapes(counting_rng: list[_CountingRandom]) -> None:
    """All four shapes must consume the same draw sequence for the same
    (n, block, seed) — the historical implementations did, because they
    shared the loop structure."""
    n, block, n_boot = 200, 30, 11
    values = _series(n, 7)
    counts = _counts(n, 8)
    flags = [c > 2 for c in counts]

    daily_mean_ci(
        values,
        block=block,
        seed=3,
        n_boot=n_boot,
        accumulation="prefix_delta",
        short_series="error",
    )
    event_mean_ci(
        values,
        counts,
        block=block,
        seed=3,
        n_boot=n_boot,
        accumulation="prefix_delta",
        short_series="error",
    )
    two_group_diff_ci(
        values,
        counts,
        values,
        counts,
        block=block,
        seed=3,
        n_boot=n_boot,
        empty_denominator="guard",
        short_series="error",
    )
    flag_split_ci(values, flags, block=block, seed=3, n_boot=n_boot)

    assert len(counting_rng) == 4
    expected = counting_rng[0].results
    assert len(expected) == n_boot * (n // block + 1)
    for rng in counting_rng[1:]:
        assert rng.results == expected


def test_clamped_and_unclamped_bounds_agree_when_series_is_long_enough() -> None:
    """short_series only bites when n < block, which never happened
    historically — recorded so the equivalence is explicit rather than
    assumed."""
    values, counts = _series(200, 71), _counts(200, 72)
    clamped = event_mean_ci(
        values,
        counts,
        block=30,
        seed=4,
        n_boot=50,
        accumulation="prefix_delta",
        short_series="clamp",
    )
    unclamped = event_mean_ci(
        values,
        counts,
        block=30,
        seed=4,
        n_boot=50,
        accumulation="prefix_delta",
        short_series="error",
    )
    assert clamped == unclamped


def test_clamp_does_not_rescue_a_short_series_it_only_moves_the_failure() -> None:
    """A finding from Step 1, recorded not fixed.

    h44_50/h52/h53 clamp the block start with ``max(n - block, 0)``, which
    looks like a short-series guard. It is not: the clamped start still
    indexes ``s + block`` past the end of the prefix array. The clamp turns
    a ValueError from ``randint`` into an IndexError a few lines later.
    Neither variant supports n < block. Correction candidate, not a Layer 1
    change.
    """
    values, counts = _series(10, 73), _counts(10, 74)
    with pytest.raises(ValueError):
        event_mean_ci(
            values,
            counts,
            block=30,
            seed=4,
            n_boot=5,
            accumulation="prefix_delta",
            short_series="error",
        )
    with pytest.raises(IndexError):
        event_mean_ci(
            values,
            counts,
            block=30,
            seed=4,
            n_boot=5,
            accumulation="prefix_delta",
            short_series="clamp",
        )
