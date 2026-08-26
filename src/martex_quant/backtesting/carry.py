"""Two-leg delta-neutral carry backtest (long spot + short perp).

Pre-registered in ``docs/hypotheses/62-delta-neutral-carry.md``.

WHY THIS IS NOT THE SPOT ENGINE
-------------------------------
``backtesting/engine.py`` is single-instrument spot by an explicit Phase 2
MVP decision, and ``portfolio/portfolio.py`` holds one symbol per instance.
A carry position is irreducibly two legs in the same asset that must be
marked together, plus a funding stream that settles on its own 8-hour
schedule and a margin account that can be liquidated independently of the
spot leg. Faking that inside the spot engine would violate the project's
backtesting rules, which is exactly why H05 deferred this build instead of
approximating it.

This module is therefore a purpose-built engine for one position shape. It
keeps the properties that matter: it marches strictly forward one day at a
time, every quantity used on day ``t`` is known at the close of ``t-1`` or
earlier, and every cost the project charges elsewhere is charged here on
BOTH legs.

THE POSITION
------------
Per symbol, with allocation ``A`` of equity:

* spot notional ``S = A / 2`` held long,
* perp margin ``M = A / 2``,
* perp short notional ``= S``.

Perp leg leverage is ``S / M = 1.0``. Liquidating the short needs a +100%
adverse move, which is why the pre-registration specifies 1x rather than
something capital-efficient: perp history here is daily closes, so an
intraday squeeze is invisible and cannot be modelled honestly.

Carry is earned on ``S``, i.e. **half** the deployed capital. Expect
roughly half of H05's gross premium figures before costs.

DAILY P&L, per symbol
---------------------
* spot leg:   ``S * r_spot``
* short perp: ``-S * r_perp``
* funding:    ``+S * sum(rates settling that day)`` — a positive rate means
  longs pay shorts, and this book is short.
* costs:      turnover on both legs at ``fee_bps + half_spread_bps``.

The first two collapse to ``S * (r_spot - r_perp)``: the basis drift. It is
the residual directional risk that makes this "delta-neutral" rather than
"delta-zero", and it is left in rather than assumed away.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import polars as pl

_BPS = 1e-4


@dataclass(frozen=True)
class CarryConfig:
    """Costs and collateralization. No defaults are hidden.

    ``collateral_ratio`` is spot notional as a fraction of the symbol's
    allocation. 0.5 is the pre-registered 1x-collateralized case: half the
    allocation is spot, half is perp margin, perp leverage 1.0.
    """

    fee_bps: float = 10.0
    half_spread_bps: float = 1.0
    collateral_ratio: float = 0.5

    @property
    def cost_rate(self) -> float:
        """Cost charged per unit of notional traded, one leg, one side."""
        return (self.fee_bps + self.half_spread_bps) * _BPS


@dataclass(frozen=True)
class CarryResult:
    """Daily streams for the whole book. All aligned to ``timestamp``."""

    daily: pl.DataFrame  # timestamp, ret, funding_ret, basis_ret, cost_ret
    equity: pl.DataFrame  # timestamp, equity, exposure
    n_symbols: int
    n_days: int


def build_symbol_frame(
    spot: pl.DataFrame,
    perp: pl.DataFrame,
    funding: pl.DataFrame,
) -> pl.DataFrame:
    """Join one symbol's three sources onto a common daily timeline.

    ``spot``   : lake D1 bars, columns ``timestamp``, ``close``.
    ``perp``   : ``day``, ``perp_close``.
    ``funding``: ``timestamp`` (8h settlement stamps), ``rate``.

    Funding is summed per calendar day, so a day carries the rates that
    actually settled on it (normally three).
    """
    # The lake stores datetime[ms, UTC]; the perp/funding caches store
    # datetime[us, UTC]. Cast every key to one unit before joining rather
    # than letting polars refuse — a silent cast here would be worse.
    day = pl.Datetime("us", "UTC")

    spot_d = (
        spot.sort("timestamp")
        .select(
            pl.col("timestamp").cast(day).dt.truncate("1d").alias("day"),
            pl.col("close").alias("spot_close"),
        )
        .group_by("day")
        .agg(pl.col("spot_close").last())
    )
    perp_d = perp.sort("day").select(
        pl.col("day").cast(day).dt.truncate("1d").alias("day"),
        "perp_close",
    )
    fund_d = (
        funding.sort("timestamp")
        .select(pl.col("timestamp").cast(day).dt.truncate("1d").alias("day"), "rate")
        .group_by("day")
        .agg(pl.col("rate").sum().alias("funding"))
    )
    return (
        spot_d.join(perp_d, on="day", how="inner")
        .join(fund_d, on="day", how="inner")
        .sort("day")
        .with_columns(
            r_spot=pl.col("spot_close") / pl.col("spot_close").shift(1) - 1.0,
            r_perp=pl.col("perp_close") / pl.col("perp_close").shift(1) - 1.0,
        )
        .drop_nulls(["r_spot", "r_perp", "funding"])
    )


def run_carry(
    frames: dict[str, pl.DataFrame],
    config: CarryConfig,
    initial_equity: float = 10_000.0,
) -> CarryResult:
    """Equal-weight, always-on carry across ``frames``.

    Marches forward one day at a time over the intersection of every
    symbol's timeline. On each day the book targets an equal spot notional
    per symbol computed from the PREVIOUS close's equity, so nothing on day
    ``t`` depends on day ``t``'s prices.
    """
    if not frames:
        raise ValueError("need at least one symbol")

    symbols = sorted(frames)
    days: set[datetime] = set(frames[symbols[0]]["day"].to_list())
    for s in symbols[1:]:
        days &= set(frames[s]["day"].to_list())
    timeline = sorted(days)
    if len(timeline) < 2:
        raise ValueError("symbols share fewer than 2 common days")

    # An optional boolean ``hold`` column gates each symbol each day (H63).
    # Absent means always-hold, so H62's stream is bit-for-bit unchanged by
    # the existence of this feature.
    lookup = {
        s: {
            row["day"]: (
                row["r_spot"],
                row["r_perp"],
                row["funding"],
                bool(row.get("hold", True)),
            )
            for row in frames[s].iter_rows(named=True)
        }
        for s in symbols
    }

    n = len(symbols)
    equity = initial_equity
    # Spot notional actually held per symbol, carried across days.
    held = {s: 0.0 for s in symbols}

    rows: list[dict[str, object]] = []
    for day in timeline:
        prev_equity = equity
        # Target notional is a function of YESTERDAY's equity only.
        target = (prev_equity / n) * config.collateral_ratio

        funding_pnl = 0.0
        basis_pnl = 0.0
        cost = 0.0
        for s in symbols:
            r_spot, r_perp, funding, hold = lookup[s][day]
            notional = held[s]

            # A gated-off symbol targets zero: capital sits in cash earning
            # nothing. It is NOT redistributed to the symbols still held --
            # concentrating into survivors would be a different strategy.
            symbol_target = target if hold else 0.0

            # Rebalance to target BEFORE the day's move, paying on both legs.
            turnover = abs(symbol_target - notional)
            cost += turnover * config.cost_rate * 2.0
            notional = symbol_target

            basis_pnl += notional * (r_spot - r_perp)
            funding_pnl += notional * funding
            # The spot leg drifts with price; that drift is next day's
            # rebalancing turnover.
            held[s] = notional * (1.0 + r_spot)

        pnl = basis_pnl + funding_pnl - cost
        equity = prev_equity + pnl
        rows.append(
            {
                "timestamp": day,
                "ret": pnl / prev_equity,
                "funding_ret": funding_pnl / prev_equity,
                "basis_ret": basis_pnl / prev_equity,
                "cost_ret": -cost / prev_equity,
                "equity": equity,
            }
        )

    frame = pl.DataFrame(rows)
    return CarryResult(
        daily=frame.select("timestamp", "ret", "funding_ret", "basis_ret", "cost_ret"),
        equity=frame.select(
            "timestamp",
            "equity",
            pl.lit(config.collateral_ratio).alias("exposure"),
        ),
        n_symbols=n,
        n_days=frame.height,
    )
