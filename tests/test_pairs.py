"""Tests for the walk-forward pairs engine (H64).

The one that matters is `test_formation_never_sees_the_trading_window`.
Pairs trading is trivially "profitable" if the hedge ratio is fitted on the
period being traded, so that separation is the strategy's only real defence
and it is asserted here rather than trusted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl

from martex_quant.backtesting.pairs import PairsConfig, form_pairs, run_pairs

FREE = {"fee_bps": 0.0, "half_spread_bps": 0.0}


def _panel(series: dict[str, list[float]]) -> pl.DataFrame:
    n = len(next(iter(series.values())))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return pl.DataFrame({"timestamp": [start + timedelta(days=i) for i in range(n)], **series})


def test_formation_never_sees_the_trading_window() -> None:
    """form_pairs must read only [lo, hi) -- the bars after hi are unseen.

    Poison the future: identical panels that differ ONLY after the
    formation window must produce identical candidates.
    """
    import random

    rng = random.Random(4)
    base = [100.0]
    for _ in range(500):
        base.append(base[-1] * (1.0 + rng.gauss(0.0, 0.02)))
    linked = [x * 1.5 * (1.0 + rng.gauss(0.0, 0.002)) for x in base]

    clean = {"A": list(linked), "B": list(base)}
    poisoned = {"A": list(linked), "B": list(base)}
    for t in range(365, len(base)):  # destroy everything after formation
        poisoned["A"][t] = 1.0
        poisoned["B"][t] = 1_000_000.0

    config = PairsConfig(z_in=2.0, z_out=0.5, max_hold_days=30)
    a = form_pairs({k: list(v) for k, v in clean.items()}, ["A", "B"], 0, 365, config)
    b = form_pairs({k: list(v) for k, v in poisoned.items()}, ["A", "B"], 0, 365, config)
    assert [(c.a, c.b) for c in a] == [(c.a, c.b) for c in b]
    if a:
        assert a[0].stats.hedge_ratio == b[0].stats.hedge_ratio
        assert a[0].stats.spread_mean == b[0].stats.spread_mean


def test_flat_book_earns_and_costs_nothing() -> None:
    """With no cointegrated pair to trade, returns must be exactly zero."""
    import random

    rng = random.Random(8)
    a = [100.0]
    b = [50.0]
    for _ in range(700):
        a.append(a[-1] * (1.0 + rng.gauss(0.0, 0.03)))
        b.append(b[-1] * (1.0 + rng.gauss(0.0, 0.03)))
    frame = _panel({"A": a, "B": b})
    config = PairsConfig(z_in=99.0, z_out=0.5, max_hold_days=30, **FREE)
    daily = run_pairs(frame, ["A", "B"], config)
    assert daily.height > 0
    assert all(r == 0.0 for r in daily["ret"].to_list())
    assert daily["n_open"].max() == 0


def test_costs_are_charged_when_positions_open() -> None:
    import random

    rng = random.Random(12)
    base = [100.0]
    for _ in range(700):
        base.append(base[-1] * (1.0 + rng.gauss(0.0, 0.02)))
    linked = [x * 2.0 * (1.0 + rng.gauss(0.0, 0.01)) for x in base]
    frame = _panel({"A": linked, "B": base})

    free = run_pairs(frame, ["A", "B"], PairsConfig(z_in=1.0, z_out=0.5, max_hold_days=30, **FREE))
    paid = run_pairs(frame, ["A", "B"], PairsConfig(z_in=1.0, z_out=0.5, max_hold_days=30))
    if free["n_open"].max() > 0:
        assert sum(paid["cost_ret"].to_list()) < 0.0
        assert sum(paid["ret"].to_list()) < sum(free["ret"].to_list())


def test_open_positions_respect_the_cap() -> None:
    import random

    rng = random.Random(21)
    series: dict[str, list[float]] = {}
    base = [100.0]
    for _ in range(700):
        base.append(base[-1] * (1.0 + rng.gauss(0.0, 0.02)))
    for i in range(8):
        series[f"S{i}"] = [x * (1.0 + i) * (1.0 + rng.gauss(0.0, 0.005)) for x in base]
    frame = _panel(series)
    config = PairsConfig(z_in=0.5, z_out=0.1, max_hold_days=60, max_open=3, **FREE)
    daily = run_pairs(frame, sorted(series), config)
    assert daily["n_open"].max() <= 3


def test_holding_cap_forces_an_exit() -> None:
    """A position must not outlive max_hold_days even if z never reverts."""
    import random

    rng = random.Random(33)
    base = [100.0]
    for _ in range(700):
        base.append(base[-1] * (1.0 + rng.gauss(0.0, 0.02)))
    linked = [x * 1.2 * (1.0 + rng.gauss(0.0, 0.008)) for x in base]
    frame = _panel({"A": linked, "B": base})
    short = run_pairs(frame, ["A", "B"], PairsConfig(z_in=1.0, z_out=0.0, max_hold_days=5, **FREE))
    long_hold = run_pairs(
        frame, ["A", "B"], PairsConfig(z_in=1.0, z_out=0.0, max_hold_days=120, **FREE)
    )
    # A tighter cap cannot hold more on average than a looser one.
    assert (short["n_open"].mean() or 0.0) <= (long_hold["n_open"].mean() or 0.0) + 1e-9


def test_a_common_shock_does_not_pass_into_pnl() -> None:
    """Both legs jumping together must not move the book.

    Note what is NOT asserted: that the whole path is unchanged. A shared
    multiplicative shock legitimately shifts the LOG spread whenever the
    hedge ratio is not 1.0 (log 2A - b*log 2B = spread + (1-b)*log 2), so
    later entry decisions differ for sound reasons. Neutrality is a claim
    about P&L on the day, and that is what is tested.
    """
    import random

    rng = random.Random(44)
    base = [100.0]
    for _ in range(700):
        base.append(base[-1] * (1.0 + rng.gauss(0.0, 0.02)))
    linked = [x * 1.5 * (1.0 + rng.gauss(0.0, 0.004)) for x in base]

    shock_day = 600
    shocked = _panel(
        {
            "A": [x * (1.5 if i >= shock_day else 1.0) for i, x in enumerate(linked)],
            "B": [x * (1.5 if i >= shock_day else 1.0) for i, x in enumerate(base)],
        }
    )
    config = PairsConfig(z_in=1.5, z_out=0.5, max_hold_days=30, **FREE)
    daily = run_pairs(shocked, ["A", "B"], config)

    # The engine's first row is panel index `formation_days`, so the shock
    # day sits at shock_day - 365 in the output.
    row = daily.row(shock_day - config.formation_days, named=True)
    assert abs(row["gross_ret"]) < 0.005, (
        f"a +50% move in BOTH legs leaked {row['gross_ret']:+.4%} into P&L"
    )
