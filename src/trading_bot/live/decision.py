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

# Cross-sectional strategies decide over ALL symbols at once; their
# exposures are fractions of TOTAL equity (not per-symbol slices).
CROSS_SECTIONAL = {"rotation"}
ROTATION_GRID = [30, 90]
ROTATION_TOP_K = 2


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


def rotation_weights(
    frames: dict[str, pl.DataFrame], lookback: int, top_k: int = ROTATION_TOP_K
) -> dict[str, float]:
    """Current dual-momentum rotation weights (stateless, from latest closes)."""
    scores: dict[str, float] = {}
    for symbol, df in frames.items():
        closes = df["close"]
        if closes.len() > lookback:
            past = closes[-1 - lookback]
            now_ = closes[-1]
            assert isinstance(past, float) and isinstance(now_, float)
            scores[symbol] = now_ / past - 1.0
    ranked = sorted(scores, key=lambda s: scores[s], reverse=True)[:top_k]
    return {s: 1.0 / top_k for s in ranked if scores[s] > 0.0}


def select_rotation_param(frames: dict[str, pl.DataFrame]) -> float:
    """Best rotation lookback on the trailing year — same selection idea as
    the walk-forward validation (train-only, by annualized Sharpe)."""
    from trading_bot.backtesting.metrics import compute_metrics
    from trading_bot.backtesting.multi import MultiBacktestConfig, run_multi_backtest
    from trading_bot.strategies.rotation import DualMomentumRotation

    best_param: float = float(ROTATION_GRID[0])
    best_sharpe = float("-inf")
    for lookback in ROTATION_GRID:
        sliced = {s: df.tail(TRAIN_DAYS) for s, df in frames.items()}
        result = run_multi_backtest(
            sliced,
            DualMomentumRotation(int(lookback)),
            config=MultiBacktestConfig(initial_cash=10_000.0),
            warmup_bars=int(lookback) + 1,
        )
        if result.equity_curve.height < 30:
            continue
        sharpe = compute_metrics(result.equity_curve, [], Interval.D1).sharpe
        if sharpe > best_sharpe:
            best_param, best_sharpe = float(lookback), sharpe
    return best_param
