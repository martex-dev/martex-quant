"""Tests for the stdlib Engle-Granger implementation (H64).

The load-bearing test here is the false-positive rate. A cointegration
test that over-rejects manufactures pairs out of noise, and a pairs
strategy built on it would look tradeable and be worthless. Calibration is
therefore checked against simulated independent random walks, not asserted.
"""

from __future__ import annotations

import math
import random

import pytest

from martex_quant.stats.cointegration import EG_CRITICAL, engle_granger


def _walk(rng: random.Random, n: int, sigma: float = 0.02) -> list[float]:
    out = [0.0]
    for _ in range(n - 1):
        out.append(out[-1] + rng.gauss(0.0, sigma))
    return out


def test_recovers_a_known_hedge_ratio() -> None:
    rng = random.Random(7)
    base = _walk(rng, 365)
    linked = [1.5 * x + rng.gauss(0.0, 0.01) for x in base]
    result = engle_granger(linked, base)
    assert result is not None
    assert result.hedge_ratio == pytest.approx(1.5, abs=0.05)
    assert result.is_cointegrated()


def test_independent_random_walks_are_not_cointegrated() -> None:
    rng = random.Random(11)
    a, b = _walk(rng, 365), _walk(rng, 365)
    result = engle_granger(a, b)
    assert result is not None
    assert not result.is_cointegrated()


def test_false_positive_rate_is_near_nominal() -> None:
    """~5% of INDEPENDENT pairs should be admitted at alpha=0.05.

    A rate far above nominal means the critical values are wrong and every
    downstream pair is suspect. Bounds are loose enough not to be flaky and
    tight enough to catch a real miscalibration.
    """
    rng = random.Random(2026)
    hits = 0
    trials = 300
    for _ in range(trials):
        result = engle_granger(_walk(rng, 365), _walk(rng, 365))
        if result is not None and result.is_cointegrated():
            hits += 1
    assert 0.01 <= hits / trials <= 0.12, f"false-positive rate {hits / trials:.1%}"


def test_critical_values_are_ordered_and_negative() -> None:
    assert EG_CRITICAL[0.01] < EG_CRITICAL[0.05] < EG_CRITICAL[0.10] < 0


def test_stricter_alpha_admits_no_more_than_looser() -> None:
    rng = random.Random(5)
    base = _walk(rng, 365)
    linked = [0.8 * x + rng.gauss(0.0, 0.015) for x in base]
    result = engle_granger(linked, base)
    assert result is not None
    if result.is_cointegrated(0.01):
        assert result.is_cointegrated(0.05)


def test_short_series_returns_none_not_a_verdict() -> None:
    """None means 'cannot say' and must never be read as 'not cointegrated'."""
    rng = random.Random(3)
    assert engle_granger(_walk(rng, 20), _walk(rng, 20)) is None


def test_mismatched_lengths_return_none() -> None:
    rng = random.Random(3)
    assert engle_granger(_walk(rng, 365), _walk(rng, 300)) is None


def test_constant_series_returns_none() -> None:
    rng = random.Random(3)
    assert engle_granger(_walk(rng, 365), [5.0] * 365) is None


def test_spread_statistics_describe_the_residual() -> None:
    rng = random.Random(9)
    base = _walk(rng, 365)
    linked = [2.0 * x + 3.0 + rng.gauss(0.0, 0.01) for x in base]
    result = engle_granger(linked, base)
    assert result is not None
    # Residual is centred by construction, and its scale matches the noise.
    assert result.spread_mean == pytest.approx(0.0, abs=1e-9)
    assert result.spread_std == pytest.approx(0.01, rel=0.4)
    assert result.intercept == pytest.approx(3.0, abs=0.05)
    assert math.isfinite(result.adf_stat)
