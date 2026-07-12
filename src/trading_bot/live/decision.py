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
CROSS_SECTIONAL = {"rotation", "rotation-stop", "crash-bounce"}
COMBINED = "combined"  # 50/50 vol-target + rotation (hypothesis 12)
ROTATION_GRID = [30, 90]
ROTATION_TOP_K = 2


def universe_symbols() -> list[str]:
    """The wide rotation universe (config/universe.json), falling back to
    the legacy 8. Rotation validated STRONGER on the wide universe
    (docs/research/wide-universe.md) and papers on it since 2026-07-12."""
    import json
    from pathlib import Path

    path = Path("config/universe.json")
    if path.exists():
        symbols: list[str] = json.loads(path.read_text(encoding="utf-8"))["symbols"]
        return symbols
    return list(SYMBOLS)


def fetch_frames(
    collector: Any, now: datetime, symbols: list[str] | None = None
) -> dict[str, pl.DataFrame]:
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=FETCH_DAYS)
    todo = symbols if symbols is not None else SYMBOLS
    return {sym: collector.fetch_ohlcv(sym, Interval.D1, start, end) for sym in todo}


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


def _histories(frames: dict[str, pl.DataFrame]) -> dict[str, Any]:
    from trading_bot.core.events import bars_from_frame

    out = {}
    for symbol, df in frames.items():
        history = History(bars_from_frame(df))
        for _ in range(df.height):
            history.advance()
        out[symbol] = history
    return out


def rotation_weights(frames: dict[str, pl.DataFrame], lookback: int) -> dict[str, float]:
    """Current VolTargetRotation weights — the same class the validation ran."""
    from trading_bot.strategies.rotation import VolTargetRotation

    return VolTargetRotation(int(lookback)).target_weights(_histories(frames))


def select_rotation_param(frames: dict[str, pl.DataFrame], *, stop: bool = False) -> float:
    """Best rotation lookback on the trailing year — same selection idea as
    the walk-forward validation (train-only, by annualized Sharpe). With
    ``stop=True`` the selection runs the H42b stop variant, mirroring the
    validation study exactly."""
    from trading_bot.backtesting.metrics import compute_metrics
    from trading_bot.backtesting.multi import MultiBacktestConfig, run_multi_backtest
    from trading_bot.strategies.rotation import VolTargetRotation
    from trading_bot.strategies.stops import StopVolTargetRotation

    best_param: float = float(ROTATION_GRID[0])
    best_sharpe = float("-inf")
    for lookback in ROTATION_GRID:
        sliced = {s: df.tail(TRAIN_DAYS) for s, df in frames.items()}
        strategy = (
            StopVolTargetRotation(int(lookback)) if stop else VolTargetRotation(int(lookback))
        )
        result = run_multi_backtest(
            sliced,
            strategy,
            config=MultiBacktestConfig(initial_cash=10_000.0),
            warmup_bars=max(int(lookback), 30) + 1,
        )
        if result.equity_curve.height < 30:
            continue
        sharpe = compute_metrics(result.equity_curve, [], Interval.D1).sharpe
        if sharpe > best_sharpe:
            best_param, best_sharpe = float(lookback), sharpe
    return best_param


def rotation_stop_weights(
    frames: dict[str, pl.DataFrame], lookback: int
) -> tuple[dict[str, float], list[str]]:
    """Current StopVolTargetRotation weights plus the stopped symbols.

    The stop latch is STATEFUL, so unlike plain rotation the strategy must
    be replayed bar by bar over the fetched history (same hysteresis-safe
    replay idea as ``current_exposure``, across the whole universe).
    """
    from trading_bot.strategies.stops import StopVolTargetRotation

    strategy = StopVolTargetRotation(int(lookback))
    bars_by_symbol = {s: bars_from_frame(df) for s, df in frames.items()}
    timeline = sorted({b.timestamp for bars in bars_by_symbol.values() for b in bars})
    cursors = dict.fromkeys(bars_by_symbol, 0)
    histories = {s: History(b) for s, b in bars_by_symbol.items()}
    weights: dict[str, float] = {}
    for ts in timeline:
        for symbol, bars in bars_by_symbol.items():
            c = cursors[symbol]
            if c < len(bars) and bars[c].timestamp == ts:
                histories[symbol].advance()
                cursors[symbol] = c + 1
        visible = {s: h for s, h in histories.items() if len(h) > 0}
        weights = strategy.target_weights(visible)
    return weights, strategy.stopped_symbols


def crash_bounce_weights(frames: dict[str, pl.DataFrame]) -> dict[str, float]:
    """Current CrashBounce weights — the same class the validation ran."""
    from trading_bot.strategies.event import CrashBounce

    return CrashBounce().target_weights(_histories(frames))
