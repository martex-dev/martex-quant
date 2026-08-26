"""Unit tests for the two-leg carry engine (H62).

These cover the four things that would silently corrupt a carry result:
the funding SIGN, delta-neutrality, costs on BOTH legs, and the absence of
look-ahead in the rebalance target.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from martex_quant.backtesting.carry import CarryConfig, build_symbol_frame, run_carry

FREE = CarryConfig(fee_bps=0.0, half_spread_bps=0.0, collateral_ratio=0.5)


def _frame(rows: list[tuple[float, float, float]]) -> pl.DataFrame:
    """Build a symbol frame directly: (r_spot, r_perp, funding) per day."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return pl.DataFrame(
        {
            "day": [start + timedelta(days=i) for i in range(len(rows))],
            "r_spot": [r[0] for r in rows],
            "r_perp": [r[1] for r in rows],
            "funding": [r[2] for r in rows],
        }
    )


def test_positive_funding_pays_the_short() -> None:
    """A positive rate means longs pay shorts, and this book IS short.

    If this test ever inverts, every carry figure flips sign.
    """
    frames = {"X": _frame([(0.0, 0.0, 0.01), (0.0, 0.0, 0.01)])}
    result = run_carry(frames, FREE, initial_equity=10_000.0)
    assert result.daily["funding_ret"].to_list()[0] > 0.0
    assert result.equity["equity"].to_list()[-1] > 10_000.0


def test_negative_funding_costs_the_short() -> None:
    frames = {"X": _frame([(0.0, 0.0, -0.01), (0.0, 0.0, -0.01)])}
    result = run_carry(frames, FREE, initial_equity=10_000.0)
    assert result.daily["funding_ret"].to_list()[0] < 0.0
    assert result.equity["equity"].to_list()[-1] < 10_000.0


def test_delta_neutral_when_legs_move_together() -> None:
    """Spot and perp moving identically must produce zero basis P&L.

    This is the property that makes the position neutral. A huge shared
    move must not show up in the return at all.
    """
    frames = {"X": _frame([(0.50, 0.50, 0.0), (-0.40, -0.40, 0.0)])}
    result = run_carry(frames, FREE, initial_equity=10_000.0)
    for value in result.daily["basis_ret"].to_list():
        assert value == pytest.approx(0.0, abs=1e-12)


def test_basis_divergence_is_not_hidden() -> None:
    """When the legs diverge, that P&L is real and must be reported."""
    frames = {"X": _frame([(0.02, 0.01, 0.0), (0.0, 0.0, 0.0)])}
    result = run_carry(frames, FREE, initial_equity=10_000.0)
    # spot +2%, perp +1% -> +1% on a notional of half the equity.
    assert result.daily["basis_ret"].to_list()[0] == pytest.approx(0.005, rel=1e-9)


def test_costs_are_charged_on_both_legs() -> None:
    """Entry turnover must be charged twice: spot leg and perp leg."""
    paid = CarryConfig(fee_bps=10.0, half_spread_bps=1.0, collateral_ratio=0.5)
    frames = {"X": _frame([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)])}
    result = run_carry(frames, paid, initial_equity=10_000.0)
    # Day 1 opens the position: notional 5,000 traded on each of two legs.
    expected = -(5_000.0 * 11e-4 * 2.0) / 10_000.0
    assert result.daily["cost_ret"].to_list()[0] == pytest.approx(expected, rel=1e-9)


def test_zero_cost_config_charges_nothing() -> None:
    frames = {"X": _frame([(0.03, 0.01, 0.001)] * 5)}
    result = run_carry(frames, FREE, initial_equity=10_000.0)
    assert all(c == pytest.approx(0.0) for c in result.daily["cost_ret"].to_list())


def test_rebalance_target_uses_only_prior_equity() -> None:
    """No look-ahead: a day's target notional cannot depend on that day.

    Two books identical up to day 3, differing only in day 3's return, must
    have identical costs on day 3 -- the target was already fixed.
    """
    a = {"X": _frame([(0.0, 0.0, 0.01), (0.0, 0.0, 0.01), (0.30, 0.30, 0.01)])}
    b = {"X": _frame([(0.0, 0.0, 0.01), (0.0, 0.0, 0.01), (-0.30, -0.30, 0.01)])}
    paid = CarryConfig(fee_bps=10.0, half_spread_bps=1.0, collateral_ratio=0.5)
    ra = run_carry(a, paid, initial_equity=10_000.0)
    rb = run_carry(b, paid, initial_equity=10_000.0)
    assert ra.daily["cost_ret"].to_list()[2] == pytest.approx(rb.daily["cost_ret"].to_list()[2])


def test_only_the_common_window_is_traded() -> None:
    """Symbols are intersected on date, never zipped by position."""
    long = _frame([(0.0, 0.0, 0.01)] * 10)
    short = _frame([(0.0, 0.0, 0.01)] * 4)
    result = run_carry({"A": long, "B": short}, FREE)
    assert result.n_days == 4
    assert result.n_symbols == 2


def test_build_symbol_frame_sums_funding_per_day() -> None:
    """Three 8-hour settlements on one day must sum, not average."""
    day = datetime(2024, 1, 1, tzinfo=UTC)
    days = [day + timedelta(days=i) for i in range(3)]
    spot = pl.DataFrame({"timestamp": days, "close": [100.0, 110.0, 120.0]}).with_columns(
        pl.col("timestamp").cast(pl.Datetime("ms", "UTC"))
    )
    perp = pl.DataFrame({"day": days, "perp_close": [100.0, 110.0, 120.0]})
    funding = pl.DataFrame(
        {
            "timestamp": [d + timedelta(hours=h) for d in days for h in (0, 8, 16)],
            "rate": [0.0001, 0.0002, 0.0003] * 3,
        }
    )
    frame = build_symbol_frame(spot, perp, funding)
    # Day 0 is dropped: no prior close, so no return.
    assert frame.height == 2
    assert frame["funding"].to_list()[0] == pytest.approx(0.0006)


def test_empty_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one symbol"):
        run_carry({}, FREE)
