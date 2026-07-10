"""Risk policy tests: caps, guards, latching kill switch, daily loss."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from trading_bot.backtesting.engine import BacktestConfig, run_backtest
from trading_bot.data.models import ohlcv_frame_from_rows
from trading_bot.execution.simulated import ExecutionConfig
from trading_bot.risk_management.policies import (
    CompositePolicy,
    DailyLossPolicy,
    DrawdownGuardPolicy,
    MaxExposurePolicy,
    mode1_policy,
    mode2_policy,
)
from trading_bot.strategies.benchmark import BuyAndHold

TS = datetime(2024, 1, 1, tzinfo=UTC)


def test_max_exposure_caps_both_directions() -> None:
    policy = MaxExposurePolicy(0.5)
    assert policy.adjust(1.0, 1000.0, 1000.0, TS) == 0.5
    assert policy.adjust(-1.0, 1000.0, 1000.0, TS) == -0.5
    assert policy.adjust(0.3, 1000.0, 1000.0, TS) == 0.3


def test_drawdown_guard_full_exposure_inside_soft_limit() -> None:
    guard = DrawdownGuardPolicy(soft_dd=0.05, hard_dd=0.10)
    assert guard.adjust(1.0, 1000.0, 1000.0, TS) == 1.0  # sets peak
    assert guard.adjust(1.0, 960.0, 1000.0, TS) == 1.0  # dd 4% < soft


def test_drawdown_guard_scales_linearly_between_limits() -> None:
    guard = DrawdownGuardPolicy(soft_dd=0.05, hard_dd=0.10)
    guard.adjust(1.0, 1000.0, 1000.0, TS)
    # dd = 7.5%: exactly halfway between soft and hard -> half exposure
    assert guard.adjust(1.0, 925.0, 1000.0, TS) == pytest.approx(0.5)


def test_drawdown_guard_kill_latches_forever() -> None:
    guard = DrawdownGuardPolicy(soft_dd=0.05, hard_dd=0.10)
    guard.adjust(1.0, 1000.0, 1000.0, TS)
    assert guard.adjust(1.0, 900.0, 1000.0, TS) == 0.0  # hard breach
    assert guard.killed
    # Full recovery does NOT re-arm:
    assert guard.adjust(1.0, 1100.0, 1000.0, TS) == 0.0


def test_daily_loss_halts_until_next_day() -> None:
    policy = DailyLossPolicy(max_daily_loss=0.02)
    day1 = TS
    assert policy.adjust(1.0, 1000.0, 1000.0, day1) == 1.0
    # 3% intraday loss -> halted for the rest of the day
    assert policy.adjust(1.0, 970.0, 1000.0, day1 + timedelta(hours=5)) == 0.0
    assert policy.adjust(1.0, 990.0, 1000.0, day1 + timedelta(hours=6)) == 0.0
    # Next day re-arms with a fresh day-start equity
    assert policy.adjust(1.0, 990.0, 1000.0, day1 + timedelta(days=1)) == 1.0


def test_composite_applies_tightest_constraint() -> None:
    policy = CompositePolicy(
        [MaxExposurePolicy(0.8), DrawdownGuardPolicy(soft_dd=0.05, hard_dd=0.10)]
    )
    policy.adjust(1.0, 1000.0, 1000.0, TS)
    # dd 7.5% -> guard halves the already-capped 0.8
    assert policy.adjust(1.0, 925.0, 1000.0, TS) == pytest.approx(0.4)


def test_policy_validation() -> None:
    with pytest.raises(ValueError):
        MaxExposurePolicy(0.0)
    with pytest.raises(ValueError):
        DrawdownGuardPolicy(soft_dd=0.2, hard_dd=0.1)
    with pytest.raises(ValueError):
        DailyLossPolicy(1.5)
    with pytest.raises(ValueError):
        CompositePolicy([])


def test_presets_construct() -> None:
    assert isinstance(mode1_policy(), CompositePolicy)
    assert isinstance(mode2_policy(), CompositePolicy)


def test_drawdown_guard_limits_crash_damage_in_engine() -> None:
    """Integration: buy-and-hold through a 50% crash. The guard must exit
    and cap the account drawdown near its hard limit; passthrough rides
    the whole crash."""
    start_ms = int(TS.timestamp() * 1000)
    closes = [100.0 + i for i in range(50)] + [149.0 - 1.5 * i for i in range(80)]
    rows = [
        [start_ms + i * 86_400_000, c, c + 0.5, c - 0.5, c, 1000.0] for i, c in enumerate(closes)
    ]
    df = ohlcv_frame_from_rows(rows)
    cfg = BacktestConfig(
        initial_cash=10_000.0,
        execution=ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=0.0),
    )

    unguarded = run_backtest(df, "T", BuyAndHold(), config=cfg)
    guarded = run_backtest(
        df,
        "T",
        BuyAndHold(),
        config=cfg,
        risk_policy=DrawdownGuardPolicy(soft_dd=0.05, hard_dd=0.15),
    )

    def max_dd(equity: pl.Series) -> float:
        dd = (equity / equity.cum_max() - 1.0).min()
        assert isinstance(dd, float)
        return dd

    assert max_dd(unguarded.equity_curve["equity"]) < -0.35  # rode the crash
    # Guard exits progressively; one extra bar of latency means slightly
    # beyond the hard limit is possible, but nowhere near the full crash.
    assert max_dd(guarded.equity_curve["equity"]) > -0.20
    assert guarded.final_equity > unguarded.final_equity
