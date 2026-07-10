"""Research harness tests: warmup semantics, selection honesty, stitching."""

from datetime import UTC, datetime

import polars as pl
import pytest

from trading_bot.backtesting.engine import BacktestConfig, run_backtest
from trading_bot.backtesting.research import walk_forward_backtest
from trading_bot.data.models import Interval, ohlcv_frame_from_rows
from trading_bot.execution.simulated import ExecutionConfig
from trading_bot.strategies.momentum import TimeSeriesMomentum

START = datetime(2024, 1, 1, tzinfo=UTC)
H1_MS = 3_600_000

ZERO_COST = BacktestConfig(
    initial_cash=1000.0,
    execution=ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=0.0),
)


def make_frame(closes: list[float]) -> pl.DataFrame:
    start_ms = int(START.timestamp() * 1000)
    rows = [[start_ms + i * H1_MS, c, c + 0.5, c - 0.5, c, 100.0] for i, c in enumerate(closes)]
    return ohlcv_frame_from_rows(rows)


# --- momentum strategy -------------------------------------------------------


def test_momentum_long_in_uptrend_flat_in_downtrend() -> None:
    up = make_frame([100.0 + i for i in range(50)])
    result = run_backtest(up, "T", TimeSeriesMomentum(lookback=5), config=ZERO_COST)
    assert result.final_equity > 1000.0

    down = make_frame([100.0 - i * 0.5 for i in range(50)])
    result = run_backtest(down, "T", TimeSeriesMomentum(lookback=5), config=ZERO_COST)
    assert result.fills == []  # never a positive trailing return: stays flat
    assert result.final_equity == 1000.0


def test_momentum_invalid_lookback() -> None:
    with pytest.raises(ValueError):
        TimeSeriesMomentum(lookback=0)


# --- engine warmup -----------------------------------------------------------


def test_warmup_primes_history_without_trading() -> None:
    up = make_frame([100.0 + i for i in range(50)])
    result = run_backtest(
        up, "T", TimeSeriesMomentum(lookback=10), config=ZERO_COST, warmup_bars=20
    )
    # Recording starts after warmup: 30 bars, and the strategy can act on
    # its very first recorded bar because history was primed.
    assert result.equity_curve.height == 30
    assert result.equity_curve["timestamp"][0] == up["timestamp"][20]
    (fill,) = result.fills
    assert fill.filled_at == up["timestamp"][21]  # signal on first live bar


def test_warmup_bounds_validated() -> None:
    frame = make_frame([100.0] * 10)
    with pytest.raises(ValueError, match="warmup_bars"):
        run_backtest(frame, "T", TimeSeriesMomentum(1), warmup_bars=10)


# --- walk-forward harness ----------------------------------------------------


def zigzag_up(n: int) -> list[float]:
    return [100.0 + i * 0.3 + (3.0 if i % 2 else 0.0) for i in range(n)]


def test_walk_forward_shapes_and_stitching() -> None:
    df = make_frame(zigzag_up(400))
    outcome = walk_forward_backtest(
        df,
        "T",
        Interval.H1,
        param_grid=[5, 20],
        strategy_factory=lambda p: TimeSeriesMomentum(int(p)),
        warmup_of=lambda p: int(p),
        train_size=100,
        test_size=50,
        config=ZERO_COST,
    )
    assert len(outcome.windows) == 6  # (400 - 100 - 50)/50 + 1
    assert outcome.oos_equity.height == 6 * 50
    # Stitched curve is continuous: each window rescaled to the prior level.
    equity = outcome.oos_equity["equity"]
    assert equity[0] == pytest.approx(1000.0)
    growth = 1.0
    for w in outcome.windows:
        growth *= w.test_growth
    assert outcome.total_growth == pytest.approx(growth, rel=1e-9)


def test_selection_ignores_test_data() -> None:
    """Leakage check: corrupting the TEST region must not change the chosen
    parameter, because selection may only read the train slice."""
    closes = zigzag_up(150)
    df_clean = make_frame(closes)
    poisoned = closes[:100] + [10_000.0 + i for i in range(50)]  # absurd test region
    df_poisoned = make_frame(poisoned)

    kwargs = dict(
        symbol="T",
        interval=Interval.H1,
        param_grid=[5, 20],
        strategy_factory=lambda p: TimeSeriesMomentum(int(p)),
        warmup_of=lambda p: int(p),
        train_size=100,
        test_size=50,
        config=ZERO_COST,
    )
    clean = walk_forward_backtest(df_clean, **kwargs)  # type: ignore[arg-type]
    dirty = walk_forward_backtest(df_poisoned, **kwargs)  # type: ignore[arg-type]
    assert [w.chosen_param for w in clean.windows] == [w.chosen_param for w in dirty.windows]


def test_walk_forward_input_validation() -> None:
    df = make_frame(zigzag_up(200))
    with pytest.raises(ValueError, match="param_grid"):
        walk_forward_backtest(
            df,
            "T",
            Interval.H1,
            [],
            lambda p: TimeSeriesMomentum(int(p)),
            lambda p: int(p),
            100,
            50,
        )
    with pytest.raises(ValueError, match="warmup"):
        walk_forward_backtest(
            df,
            "T",
            Interval.H1,
            [150],
            lambda p: TimeSeriesMomentum(int(p)),
            lambda p: int(p),
            100,
            50,
        )
