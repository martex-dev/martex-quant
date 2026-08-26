"""Unit tests for hypothesis 06/07 strategies."""

from datetime import UTC, datetime

import polars as pl
import pytest

from martex_quant.backtesting.engine import BacktestConfig, run_backtest
from martex_quant.data.models import ohlcv_frame_from_rows
from martex_quant.execution.simulated import ExecutionConfig
from martex_quant.strategies.breakout import DonchianBreakout
from martex_quant.strategies.vol_target import VolTargetMomentum

START = datetime(2024, 1, 1, tzinfo=UTC)
DAY_MS = 86_400_000

ZERO_COST = BacktestConfig(
    initial_cash=1000.0,
    execution=ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=0.0),
)


def make_frame(closes: list[float], spread: float = 0.5) -> pl.DataFrame:
    start_ms = int(START.timestamp() * 1000)
    rows = [
        [start_ms + i * DAY_MS, c, c + spread, c - spread, c, 100.0] for i, c in enumerate(closes)
    ]
    return ohlcv_frame_from_rows(rows)


# --- VolTargetMomentum --------------------------------------------------------


def test_vol_target_sizes_down_in_high_vol() -> None:
    calm = [100.0 + i * 0.2 + (0.1 if i % 2 else 0.0) for i in range(80)]
    wild = [100.0 + i * 0.2 + (6.0 if i % 2 else 0.0) for i in range(80)]
    strategy_calm = VolTargetMomentum(lookback=10)
    strategy_wild = VolTargetMomentum(lookback=10)

    calm_result = run_backtest(make_frame(calm), "T", strategy_calm, config=ZERO_COST)
    wild_result = run_backtest(make_frame(wild), "T", strategy_wild, config=ZERO_COST)

    calm_exp = calm_result.equity_curve["exposure"][-1]
    wild_exp = wild_result.equity_curve["exposure"][-1]
    assert calm_exp == pytest.approx(1.0, abs=0.01)  # low vol -> full size (capped)
    assert 0.0 < wild_exp < 0.5  # high vol -> sized down


def test_vol_target_flat_without_momentum() -> None:
    down = [100.0 - i * 0.3 for i in range(80)]
    result = run_backtest(make_frame(down), "T", VolTargetMomentum(lookback=10), config=ZERO_COST)
    assert result.fills == []


def test_vol_target_exposure_quantized() -> None:
    strategy = VolTargetMomentum(lookback=5)
    wiggle = [100.0 + i * 0.5 + (1.5 if i % 3 == 0 else 0.0) for i in range(60)]
    result = run_backtest(make_frame(wiggle), "T", strategy, config=ZERO_COST)
    for exposure in result.equity_curve["exposure"].to_list():
        if exposure > 0:
            # Quantized targets (0.05 steps); realized exposure drifts with
            # price between rebalances, so allow small tolerance.
            nearest = round(exposure * 20.0) / 20.0
            assert abs(exposure - nearest) < 0.02


def test_vol_target_validation() -> None:
    with pytest.raises(ValueError):
        VolTargetMomentum(lookback=0)
    with pytest.raises(ValueError):
        VolTargetMomentum(lookback=5, target_vol_annual=0.0)
    with pytest.raises(ValueError):
        VolTargetMomentum(lookback=5, vol_window=2)


# --- DonchianBreakout ---------------------------------------------------------


def test_donchian_enters_on_breakout_exits_on_channel_break() -> None:
    # Range 100 +/- 1 for 30 bars, breakout rally, then collapse.
    closes = [100.0 + (1.0 if i % 2 else -1.0) for i in range(30)]
    closes += [103.0 + i * 1.5 for i in range(15)]  # breakout + trend
    closes += [125.0 - i * 3.0 for i in range(12)]  # collapse through exit channel
    result = run_backtest(make_frame(closes), "T", DonchianBreakout(channel=20), config=ZERO_COST)

    assert len(result.fills) == 2  # one entry, one exit
    entry, exit_ = result.fills
    assert entry.side.value == "buy"
    assert exit_.side.value == "sell"
    assert result.final_equity > 1000.0  # caught the trend, exited on the way down


def test_donchian_stays_flat_in_range() -> None:
    closes = [100.0 + (1.0 if i % 2 else -1.0) for i in range(100)]
    result = run_backtest(make_frame(closes), "T", DonchianBreakout(channel=20), config=ZERO_COST)
    assert result.fills == []


def test_donchian_validation() -> None:
    with pytest.raises(ValueError):
        DonchianBreakout(channel=3)
