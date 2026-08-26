"""Walk-forward research harness: honest parameter selection.

For each window: evaluate every parameter on the TRAIN slice only, pick the
best by annualized Sharpe, run that single parameter on the TEST slice
(with warmup fed from bars BEFORE the test start — past data, no leakage),
and stitch the test slices into one out-of-sample equity curve.

Each test window starts flat, so the stitched curve pays a fresh entry at
every window boundary — a conservative artifact, never an optimistic one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import polars as pl

from martex_quant.backtesting.engine import BacktestConfig, run_backtest
from martex_quant.backtesting.metrics import compute_metrics
from martex_quant.backtesting.walkforward import WalkForwardWindow, walk_forward_windows
from martex_quant.data.models import Interval
from martex_quant.strategies.base import Strategy


@dataclass(frozen=True)
class WindowOutcome:
    window: WalkForwardWindow
    chosen_param: float
    train_sharpe: float
    test_growth: float  # test final equity / test initial equity
    n_test_fills: int


@dataclass(frozen=True)
class WalkForwardOutcome:
    symbol: str
    windows: list[WindowOutcome]
    oos_equity: pl.DataFrame  # stitched, timestamp/equity/exposure

    @property
    def total_growth(self) -> float:
        first = self.oos_equity["equity"][0]
        last = self.oos_equity["equity"][-1]
        assert isinstance(first, float) and isinstance(last, float)
        return last / first


def walk_forward_backtest(
    df: pl.DataFrame,
    symbol: str,
    interval: Interval,
    param_grid: Sequence[float],
    strategy_factory: Callable[[float], Strategy],
    warmup_of: Callable[[float], int],
    train_size: int,
    test_size: int,
    config: BacktestConfig | None = None,
) -> WalkForwardOutcome:
    if not param_grid:
        raise ValueError("param_grid must not be empty")
    cfg = config if config is not None else BacktestConfig()
    max_warmup = max(warmup_of(p) for p in param_grid)
    if max_warmup >= train_size:
        raise ValueError("largest warmup must be smaller than train_size")

    windows = walk_forward_windows(df.height, train_size, test_size)
    outcomes: list[WindowOutcome] = []
    stitched: list[pl.DataFrame] = []
    level = cfg.initial_cash

    for window in windows:
        train_df = df.slice(window.train_start, train_size)
        chosen, train_sharpe = _select_param(
            train_df, symbol, interval, param_grid, strategy_factory, warmup_of, cfg
        )

        # Warmup for the test run comes from bars BEFORE test_start — all in
        # the past relative to every traded test bar.
        warmup = warmup_of(chosen)
        test_slice_start = window.test_start - warmup
        test_df = df.slice(test_slice_start, warmup + test_size)
        result = run_backtest(
            test_df, symbol, strategy_factory(chosen), config=cfg, warmup_bars=warmup
        )

        curve = result.equity_curve
        first = curve["equity"][0]
        last = curve["equity"][-1]
        assert isinstance(first, float) and isinstance(last, float)
        stitched.append(curve.with_columns(pl.col("equity") * (level / first)))
        level *= last / first

        outcomes.append(
            WindowOutcome(
                window=window,
                chosen_param=chosen,
                train_sharpe=train_sharpe,
                test_growth=last / first,
                n_test_fills=len(result.fills),
            )
        )

    return WalkForwardOutcome(symbol=symbol, windows=outcomes, oos_equity=pl.concat(stitched))


def select_param(
    train_df: pl.DataFrame,
    symbol: str,
    interval: Interval,
    param_grid: Sequence[float],
    strategy_factory: Callable[[float], Strategy],
    warmup_of: Callable[[float], int],
    config: BacktestConfig | None = None,
) -> tuple[float, float]:
    """Public wrapper: best parameter on a training frame by annualized
    Sharpe. Used by the walk-forward harness and the live/paper selector,
    so research and production share one selection code path."""
    cfg = config if config is not None else BacktestConfig()
    return _select_param(train_df, symbol, interval, param_grid, strategy_factory, warmup_of, cfg)


def _select_param(
    train_df: pl.DataFrame,
    symbol: str,
    interval: Interval,
    param_grid: Sequence[float],
    strategy_factory: Callable[[float], Strategy],
    warmup_of: Callable[[float], int],
    cfg: BacktestConfig,
) -> tuple[float, float]:
    """Best parameter on the train slice by annualized Sharpe.

    Every parameter is evaluated over the identical post-max-warmup span so
    the comparison is apples to apples. Deterministic tie-break: grid order.
    """
    shared_warmup = max(warmup_of(p) for p in param_grid)
    best_param: float | None = None
    best_sharpe = float("-inf")
    for param in param_grid:
        result = run_backtest(
            train_df, symbol, strategy_factory(param), config=cfg, warmup_bars=shared_warmup
        )
        metrics = compute_metrics(result.equity_curve, result.fills, interval)
        if metrics.sharpe > best_sharpe:
            best_param = param
            best_sharpe = metrics.sharpe
    assert best_param is not None
    return best_param, best_sharpe
