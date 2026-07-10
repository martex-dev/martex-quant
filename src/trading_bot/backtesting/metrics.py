"""Performance metrics over backtest results.

Includes the probabilistic/deflated Sharpe machinery (Bailey & López de
Prado) — the tools that catch self-deception when many strategy variants
have been tried. Sharpe inputs there are PER-PERIOD (not annualized).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from statistics import NormalDist

import polars as pl

from trading_bot.core.events import Fill
from trading_bot.data.models import Interval

_MS_PER_YEAR = 365.25 * 24 * 3_600_000
_EULER_GAMMA = 0.5772156649015329
_NORMAL = NormalDist()


@dataclass(frozen=True)
class RoundTrip:
    """One completed position: opened from flat, closed back to flat (or
    flipped). ``pnl`` is realized and includes all fees."""

    entry_at: datetime
    exit_at: datetime
    pnl: float


@dataclass(frozen=True)
class Metrics:
    n_bars: int
    total_return_pct: float
    cagr_pct: float
    sharpe: float  # annualized
    max_drawdown_pct: float
    time_in_market_pct: float
    n_round_trips: int
    win_rate_pct: float | None  # None when there are no round trips
    profit_factor: float | None  # None when there are no losing trips
    total_fees: float

    def to_text(self) -> str:
        pf = f"{self.profit_factor:.2f}" if self.profit_factor is not None else "n/a"
        wr = f"{self.win_rate_pct:.1f}%" if self.win_rate_pct is not None else "n/a"
        return "\n".join(
            [
                f"bars: {self.n_bars}   round trips: {self.n_round_trips}",
                f"total return: {self.total_return_pct:+.2f}%   CAGR: {self.cagr_pct:+.2f}%",
                f"sharpe (ann.): {self.sharpe:.2f}   max drawdown: {self.max_drawdown_pct:.2f}%",
                f"win rate: {wr}   profit factor: {pf}",
                f"time in market: {self.time_in_market_pct:.1f}%   "
                f"fees paid: {self.total_fees:.2f}",
            ]
        )


def round_trips(fills: list[Fill]) -> list[RoundTrip]:
    """Pair fills into round trips with average-cost accounting.

    A trip closes when the position returns to zero; a sign flip closes the
    old trip and opens a new one at the fill price. A still-open position at
    the end is NOT reported (its PnL is unrealized).
    """
    trips: list[RoundTrip] = []
    position = 0.0
    avg_price = 0.0
    realized = 0.0
    entry_at: datetime | None = None

    for fill in fills:
        qty = fill.signed_quantity
        if position == 0.0:
            entry_at = fill.filled_at
            position = qty
            avg_price = fill.price
            realized = -fill.fee
        elif position * qty > 0:  # adding to the position
            avg_price = (avg_price * abs(position) + fill.price * abs(qty)) / (
                abs(position) + abs(qty)
            )
            position += qty
            realized -= fill.fee
        else:  # reducing, closing, or flipping
            close_qty = min(abs(qty), abs(position))
            direction = 1.0 if position > 0 else -1.0
            realized += direction * close_qty * (fill.price - avg_price) - fill.fee
            new_position = position + qty
            closed = new_position == 0.0 or position * new_position < 0
            if closed:
                assert entry_at is not None
                trips.append(RoundTrip(entry_at, fill.filled_at, realized))
                realized = 0.0
                if position * new_position < 0:  # flipped: a new trip opens now
                    entry_at = fill.filled_at
                    avg_price = fill.price
                else:
                    entry_at = None
            position = new_position
    return trips


def compute_metrics(
    equity_curve: pl.DataFrame,
    fills: list[Fill],
    interval: Interval,
) -> Metrics:
    equity = equity_curve["equity"]
    n_bars = equity.len()
    if n_bars < 2:
        raise ValueError("need at least 2 bars to compute metrics")

    initial = float(equity[0])
    final = float(equity[-1])
    periods_per_year = _MS_PER_YEAR / interval.milliseconds

    returns = equity.pct_change().drop_nulls()
    mean = returns.mean()
    std = returns.std()
    sharpe = 0.0
    if isinstance(mean, float) and isinstance(std, float) and std > 0.0:
        sharpe = mean / std * math.sqrt(periods_per_year)

    years = (n_bars - 1) / periods_per_year
    if years > 0 and final > 0:
        # Annualizing a short sample can overflow float range; that just
        # means "absurdly large", so report infinity rather than crash.
        try:
            cagr = (final / initial) ** (1.0 / years) - 1.0
        except OverflowError:
            cagr = math.inf
    else:
        cagr = -1.0

    drawdown = (equity / equity.cum_max() - 1.0).min()
    max_dd = float(drawdown) if isinstance(drawdown, float) else 0.0

    in_market_mean = (equity_curve["exposure"].abs() > 1e-9).mean()
    time_in_market = in_market_mean if isinstance(in_market_mean, float) else 0.0

    trips = round_trips(fills)
    wins = [t.pnl for t in trips if t.pnl > 0]
    losses = [t.pnl for t in trips if t.pnl <= 0]
    win_rate = 100.0 * len(wins) / len(trips) if trips else None
    profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) < 0 else None

    return Metrics(
        n_bars=n_bars,
        total_return_pct=100.0 * (final / initial - 1.0),
        cagr_pct=100.0 * cagr,
        sharpe=sharpe,
        max_drawdown_pct=100.0 * max_dd,
        time_in_market_pct=100.0 * time_in_market,
        n_round_trips=len(trips),
        win_rate_pct=win_rate,
        profit_factor=profit_factor,
        total_fees=sum(f.fee for f in fills),
    )


def probabilistic_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    benchmark_sharpe: float = 0.0,
) -> float:
    """P(true Sharpe > benchmark) given a PER-PERIOD observed Sharpe.

    Corrects for short samples and non-normal returns. Use with
    ``expected_max_sharpe`` as the benchmark to get the deflated Sharpe
    ratio when many strategy variants were tried (Phase 3 workflow).
    """
    if n_obs < 2:
        raise ValueError("need at least 2 observations")
    denom_sq = 1.0 - skew * sharpe + (kurtosis - 1.0) / 4.0 * sharpe**2
    if denom_sq <= 0.0:
        raise ValueError("invalid skew/kurtosis combination for this Sharpe level")
    z = (sharpe - benchmark_sharpe) * math.sqrt(n_obs - 1.0) / math.sqrt(denom_sq)
    return _NORMAL.cdf(z)


def expected_max_sharpe(n_trials: int, trial_sharpe_variance: float) -> float:
    """Expected maximum PER-PERIOD Sharpe among ``n_trials`` unskilled trials.

    The benchmark a strategy must beat when it was selected as the best of
    many attempts — the heart of the deflated Sharpe ratio.
    """
    if n_trials < 2:
        raise ValueError("need at least 2 trials")
    if trial_sharpe_variance < 0:
        raise ValueError("variance must be non-negative")
    e = math.e
    return math.sqrt(trial_sharpe_variance) * (
        (1.0 - _EULER_GAMMA) * _NORMAL.inv_cdf(1.0 - 1.0 / n_trials)
        + _EULER_GAMMA * _NORMAL.inv_cdf(1.0 - 1.0 / (n_trials * e))
    )
