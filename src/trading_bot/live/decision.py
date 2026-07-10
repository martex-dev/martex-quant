"""The daily decision core, shared by the paper trader and the MT5 runner.

One code path produces signals for both — any divergence between paper and
live behavior is then an execution difference, never a logic difference.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl

from trading_bot.backtesting.history import History
from trading_bot.backtesting.research import select_param
from trading_bot.core.events import bars_from_frame
from trading_bot.data.models import Interval
from trading_bot.strategies.base import Strategy
from trading_bot.strategies.breakout import DonchianBreakout
from trading_bot.strategies.vol_target import VolTargetMomentum

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]

STRATEGIES: dict[str, tuple[list[float], Callable[[float], Strategy], Callable[[float], int]]] = {
    "vol-target": (
        [7, 14, 30, 60, 90, 180],
        lambda p: VolTargetMomentum(int(p)),
        lambda p: max(int(p), 30) + 1,
    ),
    "donchian": (
        [10, 20, 40, 55, 80, 120],
        lambda p: DonchianBreakout(int(p)),
        lambda p: int(p) + 1,
    ),
}

RESELECT_DAYS = 90
TRAIN_DAYS = 365
FETCH_DAYS = 560  # train + max warmup + slack


def fetch_frames(collector: Any, now: datetime) -> dict[str, pl.DataFrame]:
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=FETCH_DAYS)
    return {sym: collector.fetch_ohlcv(sym, Interval.D1, start, end) for sym in SYMBOLS}


def needs_reselect(last_reselect: str | None, params: dict[str, Any], now: datetime) -> bool:
    if last_reselect is None or not params:
        return True
    return (now - datetime.fromisoformat(last_reselect)).days >= RESELECT_DAYS


def reselect_params(
    frames: dict[str, pl.DataFrame],
    strategy_name: str,
) -> dict[str, float]:
    grid, factory, warmup_of = STRATEGIES[strategy_name]
    params: dict[str, float] = {}
    for symbol, df in frames.items():
        param, _ = select_param(df.tail(TRAIN_DAYS), symbol, Interval.D1, grid, factory, warmup_of)
        params[symbol] = param
    return params


def current_exposure(strategy_name: str, param: float, df: pl.DataFrame) -> float:
    """Replay the strategy over history so stateful strategies (Donchian
    hysteresis) reconstruct their position correctly."""
    _, factory, _ = STRATEGIES[strategy_name]
    strategy = factory(param)
    bars = bars_from_frame(df)
    history = History(bars)
    exposure = 0.0
    for _ in bars:
        history.advance()
        exposure = strategy.on_bar(history)
    return exposure


def utcnow() -> datetime:
    return datetime.now(tz=UTC)
