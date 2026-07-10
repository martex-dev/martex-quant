"""The Phase 3 candidate, as a reusable return stream.

Daily TSMOM, long/flat, equal-weight across the 8-symbol universe,
lookback re-selected each 90 days by 1-year-train walk-forward
(docs/research/phase3-verdict.md). Used by the prop-firm simulator and
any future analysis that needs "the candidate's" out-of-sample returns.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from trading_bot.backtesting.engine import BacktestConfig
from trading_bot.backtesting.research import walk_forward_backtest
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.strategies.momentum import TimeSeriesMomentum

CANDIDATE_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LTCUSDT",
]
CANDIDATE_GRID = [7, 14, 30, 60, 90, 180]


def candidate_oos_daily_returns(lake: Path) -> list[float]:
    """Equal-weight portfolio daily returns of the candidate's stitched
    walk-forward OOS curves. Fees/spread/slippage already inside."""
    store = ParquetStore(lake)
    per_symbol: list[pl.Series] = []
    for symbol in CANDIDATE_SYMBOLS:
        outcome = walk_forward_backtest(
            df=store.read(symbol, Interval.D1),
            symbol=symbol,
            interval=Interval.D1,
            param_grid=CANDIDATE_GRID,
            strategy_factory=lambda p: TimeSeriesMomentum(int(p)),
            warmup_of=lambda p: int(p) + 1,
            train_size=365,
            test_size=90,
            config=BacktestConfig(initial_cash=10_000.0),
        )
        per_symbol.append(outcome.oos_equity["equity"].pct_change().fill_null(0.0))

    n = min(s.len() for s in per_symbol)
    total = pl.Series([0.0] * n)
    for series in per_symbol:
        total = total + series.tail(n)
    return list((total / len(per_symbol)).to_list())
