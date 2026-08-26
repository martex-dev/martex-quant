"""Tests for panel-based outcome measurement.

Every test here exists because the corresponding mistake would manufacture an
edge that is not there: pricing an entry before we could have traded, carrying
a stale price forward across an unobserved horizon, or quietly dropping a dead
token out of the denominator.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from martex_quant.meme.panel import DELISTED_RETURN, Observation, measure_launch

T0 = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def obs(minute: float, price: float | None, *, liquidity: float = 5_000.0, alive: bool = True):
    return Observation(
        at=T0 + timedelta(minutes=minute), price=price, liquidity=liquidity, alive=alive
    )


def test_entry_is_first_observation_after_discovery() -> None:
    series = [obs(0, 1.0), obs(5, 2.0), obs(10, 3.0)]
    outcome = measure_launch("p", series, T0 + timedelta(minutes=1), horizons_min=(15,))
    assert outcome.entry_price == 2.0
    assert outcome.entry_at == T0 + timedelta(minutes=5)


def test_observation_at_discovery_instant_is_not_tradable() -> None:
    """Strictly-after, not at-or-after: we cannot trade the tick we learn from."""
    series = [obs(0, 1.0), obs(5, 2.0)]
    outcome = measure_launch("p", series, T0, horizons_min=(15,))
    assert outcome.entry_price == 2.0


def test_single_observation_is_unmeasurable() -> None:
    outcome = measure_launch("p", [obs(0, 1.0)], T0)
    assert not outcome.measurable
    assert outcome.reason == "fewer than 2 observations"


def test_no_priceable_observation_after_discovery() -> None:
    series = [obs(0, 1.0), obs(5, None, alive=False)]
    outcome = measure_launch("p", series, T0)
    assert not outcome.measurable
    assert outcome.reason == "no priceable observation after discovery"


def test_returns_and_excursions_within_horizon() -> None:
    series = [obs(0, 1.0), obs(5, 1.0), obs(10, 4.0), obs(15, 0.5), obs(20, 2.0)]
    outcome = measure_launch("p", series, T0, horizons_min=(15,))
    assert outcome.entry_price == 1.0  # entry at minute 5
    # Window covers elapsed 0,5,10,15 (i.e. observations at minutes 5..20).
    assert outcome.returns[15] == pytest.approx(1.0)  # last in window: 2.0 vs 1.0
    assert outcome.mfe[15] == pytest.approx(3.0)  # peak 4.0
    assert outcome.mae[15] == pytest.approx(-0.5)  # trough 0.5


def test_unobserved_horizon_is_absent_not_carried_forward() -> None:
    """A pool watched for 20 minutes has no 24-hour outcome."""
    series = [obs(m, 1.0) for m in (0, 5, 10, 15, 20)]
    outcome = measure_launch("p", series, T0, horizons_min=(15, 60, 1440))
    assert 15 in outcome.returns
    assert 60 not in outcome.returns
    assert 1440 not in outcome.returns


def test_delisting_books_a_total_loss_and_is_not_dropped() -> None:
    series = [obs(0, 1.0), obs(5, 1.0), obs(10, None, alive=False), obs(20, None, alive=False)]
    outcome = measure_launch("p", series, T0, horizons_min=(15,))
    assert outcome.measurable
    assert outcome.delisted_at_min == pytest.approx(5.0)
    assert outcome.returns[15] == pytest.approx(DELISTED_RETURN)
    assert outcome.mae[15] == pytest.approx(DELISTED_RETURN)


def test_returns_never_below_total_loss() -> None:
    """You cannot lose more than the stake on a spot position."""
    series = [obs(0, 1.0), obs(5, 1.0), obs(20, None, alive=False)]
    outcome = measure_launch("p", series, T0, horizons_min=(15,))
    assert outcome.returns[15] >= DELISTED_RETURN
    assert outcome.mae[15] >= DELISTED_RETURN


def test_horizon_tolerance_rejects_barely_covered_window() -> None:
    """A window covering 6 of 60 minutes does not measure the 60m horizon."""
    series = [obs(0, 1.0), obs(5, 1.0), obs(11, 1.0)]
    outcome = measure_launch("p", series, T0, horizons_min=(60,))
    assert 60 not in outcome.returns


def test_peak_return_and_time_to_peak_measured_from_entry() -> None:
    series = [obs(0, 1.0), obs(5, 1.0), obs(15, 6.0), obs(25, 2.0)]
    outcome = measure_launch("p", series, T0, horizons_min=(30,))
    assert outcome.peak_return == pytest.approx(5.0)
    assert outcome.minutes_to_peak == pytest.approx(10.0)  # entry at minute 5


def test_entry_liquidity_is_recorded_for_cost_modelling() -> None:
    series = [obs(0, 1.0, liquidity=1_000.0), obs(5, 1.0, liquidity=7_500.0)]
    outcome = measure_launch("p", series, T0, horizons_min=(15,))
    assert outcome.entry_liquidity == 7_500.0


def test_to_row_covers_all_horizons() -> None:
    series = [obs(m, 1.0) for m in (0, 5, 10, 15, 20)]
    row = measure_launch("p", series, T0).to_row()
    for horizon in (15, 30, 60, 120, 240, 720, 1440):
        assert f"ret_{horizon}m" in row
    assert row["ret_15m"] == pytest.approx(0.0)
    assert row["ret_1440m"] is None
