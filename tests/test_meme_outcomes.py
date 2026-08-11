"""Tests for forward-outcome measurement on launch cohorts.

The leakage guards are the important ones. Entry must never be priced before
the bar we could have acted on, and a horizon we did not observe must come back
absent rather than as a fabricated flat return.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trading_bot.meme.outcomes import measure
from trading_bot.meme.sources.geckoterminal import Bar

T0 = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def bars(*specs: tuple[int, float, float, float, float]) -> list[Bar]:
    """Build bars from (minute_offset, open, high, low, close) tuples."""
    return [
        Bar(ts=T0 + timedelta(minutes=m), open=o, high=h, low=lo, close=c, volume=1_000.0)
        for m, o, h, lo, c in specs
    ]


def test_entry_uses_first_bar_strictly_after_observation() -> None:
    """The bar we observed during is not tradable; the next one is."""
    series = bars(
        (0, 1.0, 1.0, 1.0, 1.0),
        (1, 2.0, 2.0, 2.0, 2.0),
        (2, 3.0, 3.0, 3.0, 3.0),
    )
    observed = T0 + timedelta(seconds=30)  # inside bar 0, before bar 1
    outcome = measure("pool", series, observed, horizons_min=(1,))
    assert outcome.entry_price == 2.0
    assert outcome.entry_at == T0 + timedelta(minutes=1)


def test_no_bar_after_observation_is_unmeasurable() -> None:
    series = bars((0, 1.0, 1.0, 1.0, 1.0))
    outcome = measure("pool", series, T0 + timedelta(minutes=5))
    assert not outcome.measurable
    assert outcome.reason == "no bar after observation"


def test_empty_bars_are_unmeasurable() -> None:
    outcome = measure("pool", [], T0)
    assert not outcome.measurable
    assert outcome.reason == "no bars returned"


def test_returns_mfe_and_mae_at_horizon() -> None:
    series = bars(
        (0, 1.0, 1.0, 1.0, 1.0),
        (1, 1.0, 3.0, 0.5, 2.0),  # entry bar: high 3.0, low 0.5
        (2, 2.0, 2.5, 1.5, 1.5),
    )
    outcome = measure("pool", series, T0 + timedelta(seconds=30), horizons_min=(1,))
    assert outcome.entry_price == 1.0
    assert outcome.returns[1] == pytest.approx(0.5)  # close 1.5 vs entry 1.0
    assert outcome.mfe[1] == pytest.approx(2.0)  # high 3.0 -> +200%
    assert outcome.mae[1] == pytest.approx(-0.5)  # low 0.5 -> -50%


def test_unobserved_horizon_is_absent_not_zero() -> None:
    """A feed that stops must not report its last price as the 24h outcome."""
    series = bars(*[(m, 1.0, 1.0, 1.0, 1.0) for m in range(0, 12)])
    outcome = measure("pool", series, T0, horizons_min=(5, 60, 1440))
    assert 5 in outcome.returns
    assert 60 not in outcome.returns
    assert 1440 not in outcome.returns


def test_death_flagged_at_first_horizon_breaching_threshold() -> None:
    """Entry is bar 1, so the crash in bar 3 lands inside horizon 2, not 1."""
    series = bars(
        (0, 1.0, 1.0, 1.0, 1.0),
        (1, 1.0, 1.0, 1.0, 1.0),  # entry bar
        (2, 1.0, 1.0, 1.0, 1.0),
        (3, 1.0, 1.0, 0.05, 0.05),  # -95%
        (4, 0.05, 0.05, 0.05, 0.05),
    )
    outcome = measure("pool", series, T0, horizons_min=(1, 2, 3))
    assert outcome.died_within_min == 2
    assert outcome.mae[1] > -0.9
    assert outcome.mae[2] <= -0.9


def test_peak_return_and_time_to_peak() -> None:
    series = bars(
        (0, 1.0, 1.0, 1.0, 1.0),
        (1, 1.0, 1.0, 1.0, 1.0),
        (2, 1.0, 5.0, 1.0, 1.2),
        (3, 1.2, 1.3, 1.0, 1.0),
    )
    outcome = measure("pool", series, T0, horizons_min=(3,))
    assert outcome.peak_return == pytest.approx(4.0)
    assert outcome.minutes_to_peak == pytest.approx(1.0)  # entry is bar 1


def test_non_positive_entry_price_is_rejected() -> None:
    series = bars((0, 1.0, 1.0, 1.0, 1.0), (1, 0.0, 0.0, 0.0, 0.0))
    outcome = measure("pool", series, T0)
    assert not outcome.measurable
    assert outcome.reason == "non-positive entry price"


def test_to_row_emits_every_requested_horizon_key() -> None:
    series = bars(*[(m, 1.0, 1.0, 1.0, 1.0) for m in range(0, 8)])
    row = measure("pool", series, T0).to_row()
    for horizon in (5, 15, 30, 60, 240, 1440):
        assert f"ret_{horizon}m" in row
        assert f"mfe_{horizon}m" in row
        assert f"mae_{horizon}m" in row
    assert row["ret_5m"] == pytest.approx(0.0)
    assert row["ret_1440m"] is None
