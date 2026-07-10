"""Unit tests for research strategies (momentum has its own in test_research)."""

from datetime import UTC, datetime

import polars as pl
import pytest

from trading_bot.backtesting.engine import BacktestConfig, run_backtest
from trading_bot.data.models import ohlcv_frame_from_rows
from trading_bot.execution.simulated import ExecutionConfig
from trading_bot.strategies.meanrev import BollingerReversion
from trading_bot.strategies.vol_filter import VolFilteredMomentum

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


# --- VolFilteredMomentum ------------------------------------------------------


def test_volfilter_long_in_calm_uptrend() -> None:
    # Steady uptrend: recent vol equals long-run vol nowhere strictly less...
    # so make late section calmer: bigger wiggles early, tiny late.
    closes = [100.0 + i * 0.5 + (2.0 if i % 2 and i < 60 else 0.0) for i in range(120)]
    result = run_backtest(
        make_frame(closes),
        "T",
        VolFilteredMomentum(lookback=10, vol_short=10, vol_long=40),
        config=ZERO_COST,
    )
    assert result.final_equity > 1000.0  # took the calm-uptrend trade


def test_volfilter_flat_when_volatile_despite_momentum() -> None:
    # Uptrend whose RECENT section is far noisier than its long baseline.
    closes = [100.0 + i * 0.5 + (8.0 if i % 2 and i >= 80 else 0.0) for i in range(120)]
    strategy = VolFilteredMomentum(lookback=10, vol_short=10, vol_long=40)
    result = run_backtest(make_frame(closes), "T", strategy, config=ZERO_COST)
    # Momentum is positive late, but the vol gate must forbid the position
    # on the noisy tail: no position open at the end.
    assert result.equity_curve["exposure"][-1] == 0.0


def test_volfilter_validation() -> None:
    with pytest.raises(ValueError):
        VolFilteredMomentum(lookback=0)
    with pytest.raises(ValueError):
        VolFilteredMomentum(lookback=5, vol_short=90, vol_long=30)


# --- BollingerReversion -------------------------------------------------------


def test_meanrev_buys_the_dip_and_exits_on_recovery() -> None:
    # Flat around 100 with mild noise, one sharp dip, then recovery.
    closes = [100.0 + (0.3 if i % 2 else -0.3) for i in range(200)]
    closes[150:156] = [90.0, 89.0, 88.0, 89.0, 95.0, 100.0]
    result = run_backtest(
        make_frame(closes), "T", BollingerReversion(band_k=2.0, window=50), config=ZERO_COST
    )
    assert len(result.fills) >= 2  # entered on the stretch, exited on recovery
    assert result.fills[0].side.value == "buy"
    assert result.final_equity > 1000.0  # bought ~90 area, price recovered


def test_meanrev_stays_flat_in_quiet_market() -> None:
    closes = [100.0 + (0.2 if i % 2 else -0.2) for i in range(120)]
    result = run_backtest(
        make_frame(closes), "T", BollingerReversion(band_k=2.5, window=50), config=ZERO_COST
    )
    assert result.fills == []


def test_meanrev_validation() -> None:
    with pytest.raises(ValueError):
        BollingerReversion(band_k=0.0)
    with pytest.raises(ValueError):
        BollingerReversion(band_k=2.0, window=1)
