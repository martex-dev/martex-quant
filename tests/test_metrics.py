"""Metrics tests: hand-computed values on crafted curves and fill sequences."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
    round_trips,
)
from martex_quant.core.events import Fill, Side
from martex_quant.data.models import Interval

START = datetime(2024, 1, 1, tzinfo=UTC)


def make_curve(equities: list[float], exposures: list[float] | None = None) -> pl.DataFrame:
    n = len(equities)
    return pl.DataFrame(
        {
            "timestamp": [START + timedelta(hours=i) for i in range(n)],
            "equity": equities,
            "exposure": exposures if exposures is not None else [1.0] * n,
        }
    )


def fill(hours: int, side: Side, qty: float, price: float, fee: float = 0.0) -> Fill:
    return Fill(START + timedelta(hours=hours), "TEST", side, qty, price, fee)


# --- round trips -------------------------------------------------------------


def test_single_winning_round_trip() -> None:
    trips = round_trips(
        [
            fill(0, Side.BUY, 10.0, 100.0, fee=1.0),
            fill(5, Side.SELL, 10.0, 110.0, fee=1.1),
        ]
    )
    assert len(trips) == 1
    assert trips[0].pnl == pytest.approx(10.0 * 10.0 - 1.0 - 1.1)
    assert trips[0].entry_at == START
    assert trips[0].exit_at == START + timedelta(hours=5)


def test_losing_short_round_trip() -> None:
    trips = round_trips(
        [
            fill(0, Side.SELL, 5.0, 100.0),
            fill(3, Side.BUY, 5.0, 104.0),
        ]
    )
    assert len(trips) == 1
    assert trips[0].pnl == pytest.approx(-20.0)  # short, price went up


def test_scale_in_uses_average_cost() -> None:
    trips = round_trips(
        [
            fill(0, Side.BUY, 10.0, 100.0),
            fill(1, Side.BUY, 10.0, 110.0),  # avg cost now 105
            fill(2, Side.SELL, 20.0, 120.0),
        ]
    )
    assert len(trips) == 1
    assert trips[0].pnl == pytest.approx(20.0 * (120.0 - 105.0))


def test_flip_closes_and_opens() -> None:
    trips = round_trips(
        [
            fill(0, Side.BUY, 10.0, 100.0),
            fill(1, Side.SELL, 25.0, 110.0),  # closes 10 long, opens 15 short
            fill(2, Side.BUY, 15.0, 105.0),  # closes the short
        ]
    )
    assert len(trips) == 2
    assert trips[0].pnl == pytest.approx(10.0 * 10.0)
    assert trips[1].pnl == pytest.approx(15.0 * (110.0 - 105.0))


def test_open_position_at_end_not_reported() -> None:
    trips = round_trips([fill(0, Side.BUY, 10.0, 100.0)])
    assert trips == []


# --- metrics ----------------------------------------------------------------


def test_flat_curve_metrics() -> None:
    m = compute_metrics(make_curve([1000.0] * 10, exposures=[0.0] * 10), [], Interval.H1)
    assert m.total_return_pct == 0.0
    assert m.sharpe == 0.0
    assert m.max_drawdown_pct == 0.0
    assert m.time_in_market_pct == 0.0
    assert m.n_round_trips == 0
    assert m.win_rate_pct is None
    assert m.profit_factor is None


def test_total_return_and_drawdown_hand_computed() -> None:
    # Peak 1200, trough 900: drawdown = 900/1200 - 1 = -25%
    m = compute_metrics(make_curve([1000.0, 1200.0, 900.0, 1100.0]), [], Interval.H1)
    assert m.total_return_pct == pytest.approx(10.0)
    assert m.max_drawdown_pct == pytest.approx(-25.0)


def test_monotonic_growth_has_positive_sharpe_no_drawdown() -> None:
    m = compute_metrics(make_curve([1000.0, 1010.0, 1021.0, 1033.0, 1046.0]), [], Interval.H1)
    assert m.sharpe > 0
    assert m.max_drawdown_pct == pytest.approx(0.0)
    assert m.cagr_pct > 0


def test_metrics_require_two_bars() -> None:
    with pytest.raises(ValueError):
        compute_metrics(make_curve([1000.0]), [], Interval.H1)


def test_report_text_renders() -> None:
    m = compute_metrics(make_curve([1000.0, 1100.0]), [], Interval.H1)
    text = m.to_text()
    assert "total return: +10.00%" in text
    assert "win rate: n/a" in text


# --- probabilistic / deflated sharpe ----------------------------------------


def test_psr_high_for_strong_sharpe_long_sample() -> None:
    assert probabilistic_sharpe_ratio(0.1, n_obs=5000) > 0.99


def test_psr_near_half_for_zero_sharpe() -> None:
    assert probabilistic_sharpe_ratio(0.0, n_obs=100) == pytest.approx(0.5)


def test_psr_penalizes_short_samples() -> None:
    long_sample = probabilistic_sharpe_ratio(0.05, n_obs=5000)
    short_sample = probabilistic_sharpe_ratio(0.05, n_obs=50)
    assert short_sample < long_sample


def test_psr_penalizes_fat_tails() -> None:
    normal = probabilistic_sharpe_ratio(0.1, n_obs=1000, skew=0.0, kurtosis=3.0)
    fat = probabilistic_sharpe_ratio(0.1, n_obs=1000, skew=-1.0, kurtosis=10.0)
    assert fat < normal


def test_expected_max_sharpe_grows_with_trials() -> None:
    few = expected_max_sharpe(n_trials=10, trial_sharpe_variance=0.01)
    many = expected_max_sharpe(n_trials=1000, trial_sharpe_variance=0.01)
    assert 0 < few < many


def test_deflated_sharpe_workflow() -> None:
    """The Phase 3 pattern: best-of-N selection must beat the noise ceiling."""
    noise_ceiling = expected_max_sharpe(n_trials=100, trial_sharpe_variance=0.02)
    dsr = probabilistic_sharpe_ratio(0.05, n_obs=2000, benchmark_sharpe=noise_ceiling)
    # A modest sharpe that was the best of 100 tries is NOT convincing:
    assert dsr < 0.95


def test_psr_input_validation() -> None:
    with pytest.raises(ValueError):
        probabilistic_sharpe_ratio(0.1, n_obs=1)
    with pytest.raises(ValueError):
        expected_max_sharpe(n_trials=1, trial_sharpe_variance=0.01)
    with pytest.raises(ValueError):
        expected_max_sharpe(n_trials=10, trial_sharpe_variance=-1.0)
