"""Multi-asset engine + rotation tests: hand-checked accounting, latency,
staggered listings, weight validation."""

from datetime import UTC, datetime

import polars as pl
import pytest

from martex_quant.backtesting.history import History
from martex_quant.backtesting.multi import (
    MultiAssetStrategy,
    MultiBacktestConfig,
    run_multi_backtest,
)
from martex_quant.data.models import ohlcv_frame_from_rows
from martex_quant.execution.simulated import ExecutionConfig
from martex_quant.strategies.rotation import DualMomentumRotation

START = datetime(2024, 1, 1, tzinfo=UTC)
DAY_MS = 86_400_000

ZERO_COST = MultiBacktestConfig(
    initial_cash=1000.0,
    execution=ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=0.0),
)


def daily_frame(closes: list[float], offset_days: int = 0) -> pl.DataFrame:
    start = int(START.timestamp() * 1000) + offset_days * DAY_MS
    rows = [[start + i * DAY_MS, c, c + 0.5, c - 0.5, c, 1e6] for i, c in enumerate(closes)]
    return ohlcv_frame_from_rows(rows)


class HoldFirstSymbol(MultiAssetStrategy):
    """Puts 50% of equity in symbol 'A' from the first decision onward."""

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        return {"A": 0.5} if "A" in histories else {}


def test_hand_checked_accounting_and_latency() -> None:
    frames = {
        "A": daily_frame([100.0, 100.0, 110.0, 120.0]),
        "B": daily_frame([50.0, 50.0, 50.0, 50.0]),
    }
    result = run_multi_backtest(frames, HoldFirstSymbol(), config=ZERO_COST)

    # Decision on day0 close; first fill at day1 OPEN (100.0): 5 units for
    # $500. Later fills are constant-mix rebalances (by design for a
    # weights-based portfolio) and are checked via the equity curve.
    a_fills = [f for f in result.fills if f.symbol == "A"]
    assert a_fills[0].price == 100.0
    assert a_fills[0].quantity == pytest.approx(5.0)
    assert a_fills[0].filled_at == frames["A"]["timestamp"][1]

    equity = result.equity_curve["equity"].to_list()
    assert equity[0] == 1000.0  # day0: nothing filled yet
    # day2 close: 5 units at 110 + cash 500 = 1050; day3: 5*120+500 = 1100.
    assert equity[2] == pytest.approx(1050.0)
    assert equity[3] == pytest.approx(1100.0)


def test_staggered_listing_joins_later() -> None:
    class EqualWeightAll(MultiAssetStrategy):
        def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
            n = len(histories)
            return {s: 1.0 / max(n, 1) for s in histories}

    frames = {
        "A": daily_frame([100.0] * 10),
        "B": daily_frame([50.0] * 6, offset_days=4),  # lists on day 4
    }
    result = run_multi_backtest(frames, EqualWeightAll(), config=ZERO_COST)
    b_fills = [f for f in result.fills if f.symbol == "B"]
    assert b_fills  # B traded once listed
    assert min(f.filled_at for f in b_fills) >= frames["B"]["timestamp"][1]


def test_invalid_weights_rejected() -> None:
    class Overweight(MultiAssetStrategy):
        def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
            return dict.fromkeys(histories, 0.9)  # sums > 1

    frames = {"A": daily_frame([100.0] * 3), "B": daily_frame([50.0] * 3)}
    with pytest.raises(ValueError, match="invalid weights"):
        run_multi_backtest(frames, Overweight(), config=ZERO_COST)


def test_warmup_suppresses_early_trading() -> None:
    frames = {"A": daily_frame([100.0 + i for i in range(10)])}
    result = run_multi_backtest(frames, HoldFirstSymbol(), config=ZERO_COST, warmup_bars=5)
    assert result.equity_curve.height == 5  # recorded only after warmup
    assert all(f.filled_at >= frames["A"]["timestamp"][6] for f in result.fills)


# --- rotation strategy ---------------------------------------------------------


def make_histories(closes: dict[str, list[float]]) -> dict[str, History]:
    out = {}
    for sym, series in closes.items():
        frame = daily_frame(series)
        from martex_quant.core.events import bars_from_frame

        history = History(bars_from_frame(frame))
        for _ in series:
            history.advance()
        out[sym] = history
    return out


def test_rotation_picks_top_two_positive() -> None:
    histories = make_histories(
        {
            "UP_BIG": [100.0, 100.0, 100.0, 150.0],  # +50%
            "UP_SMALL": [100.0, 100.0, 100.0, 110.0],  # +10%
            "UP_TINY": [100.0, 100.0, 100.0, 101.0],  # +1%
            "DOWN": [100.0, 100.0, 100.0, 80.0],  # -20%
        }
    )
    weights = DualMomentumRotation(lookback=3, top_k=2).target_weights(histories)
    assert weights == {"UP_BIG": 0.5, "UP_SMALL": 0.5}


def test_rotation_absolute_gate_leaves_cash() -> None:
    histories = make_histories(
        {
            "UP": [100.0, 100.0, 100.0, 120.0],
            "FLATTISH": [100.0, 100.0, 100.0, 99.0],  # negative: gated out
            "DOWN": [100.0, 100.0, 100.0, 70.0],
        }
    )
    weights = DualMomentumRotation(lookback=3, top_k=2).target_weights(histories)
    assert weights == {"UP": 0.5}  # second slot stays in cash


def test_rotation_all_negative_goes_flat() -> None:
    histories = make_histories({"A": [100.0, 100.0, 100.0, 90.0], "B": [100.0, 100.0, 100.0, 95.0]})
    assert DualMomentumRotation(lookback=3, top_k=2).target_weights(histories) == {}


def test_rotation_ignores_symbols_without_enough_history() -> None:
    histories = make_histories({"LONG": [100.0] * 5 + [120.0], "NEW": [100.0, 130.0]})
    weights = DualMomentumRotation(lookback=5, top_k=2).target_weights(histories)
    assert "NEW" not in weights


def test_rotation_validation() -> None:
    with pytest.raises(ValueError):
        DualMomentumRotation(lookback=0)
    with pytest.raises(ValueError):
        DualMomentumRotation(lookback=5, top_k=0)


def test_vol_target_rotation_scales_down_in_high_vol() -> None:
    from martex_quant.strategies.rotation import VolTargetRotation

    calm = [100.0 * (1.002**i) for i in range(40)]
    wild = [100.0 * (1.002**i) * (1 + (0.06 if i % 2 else -0.02)) for i in range(40)]
    calm_h = make_histories({"A": calm, "B": [c * 0.5 for c in calm]})
    wild_h = make_histories({"A": wild, "B": [c * 0.5 for c in wild]})

    strategy = VolTargetRotation(lookback=10, vol_window=20)
    calm_w = strategy.target_weights(calm_h)
    wild_w = strategy.target_weights(wild_h)
    assert sum(calm_w.values()) > 0.9  # low vol -> near-full allocation
    assert 0 < sum(wild_w.values()) < 0.5  # high vol -> scaled down


def test_vol_target_rotation_stays_out_without_history() -> None:
    from martex_quant.strategies.rotation import VolTargetRotation

    short = make_histories({"A": [100.0, 105.0, 110.0, 120.0]})
    assert VolTargetRotation(lookback=2, vol_window=30).target_weights(short) == {}


def test_crash_bounce_triggers_only_after_btc_crash() -> None:
    from martex_quant.strategies.event import CrashBounce

    crash = make_histories(
        {
            "BTCUSDT": [100.0, 100.0, 100.0, 95.0],  # -5% today
            "ETHUSDT": [50.0, 50.0, 50.0, 49.0],
            "SOLUSDT": [10.0, 10.0, 10.0, 9.5],
        }
    )
    weights = CrashBounce().target_weights(crash)
    assert weights == {"ETHUSDT": 0.5, "SOLUSDT": 0.5}  # EW alts, no BTC

    quiet = make_histories(
        {
            "BTCUSDT": [100.0, 100.0, 100.0, 99.0],  # -1%: no trigger
            "ETHUSDT": [50.0, 50.0, 50.0, 49.0],
        }
    )
    assert CrashBounce().target_weights(quiet) == {}


def test_crash_bounce_validation() -> None:
    import pytest as _pytest

    from martex_quant.strategies.event import CrashBounce

    with _pytest.raises(ValueError):
        CrashBounce(threshold=0.03)
