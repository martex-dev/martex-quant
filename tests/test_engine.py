"""Engine tests, including the three Phase 2 exit criteria:

1. A known-answer strategy's fills and equity reproduce hand-computed values.
2. Look-ahead is architecturally impossible (clairvoyant strategy fails).
3. Buy-and-hold matches an independent manual calculation of the cost model.
"""

from datetime import UTC, datetime

import polars as pl
import pytest

from martex_quant.backtesting.engine import BacktestConfig, run_backtest
from martex_quant.backtesting.history import History
from martex_quant.core.events import Side
from martex_quant.data.models import ohlcv_frame_from_rows
from martex_quant.execution.simulated import ExecutionConfig
from martex_quant.strategies.base import Strategy
from martex_quant.strategies.benchmark import BuyAndHold, Flat, SmaCross

START = datetime(2024, 1, 1, tzinfo=UTC)
H1_MS = 3_600_000

ZERO_COST = BacktestConfig(
    initial_cash=1000.0,
    execution=ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=0.0),
)


def make_frame(ohlcv: list[tuple[float, float, float, float, float]]) -> pl.DataFrame:
    start_ms = int(START.timestamp() * 1000)
    rows = [[start_ms + i * H1_MS, o, h, lo, c, v] for i, (o, h, lo, c, v) in enumerate(ohlcv)]
    return ohlcv_frame_from_rows(rows)


FOUR_BARS = make_frame(
    [
        (100.0, 111.0, 99.0, 110.0, 50.0),
        (110.0, 116.0, 104.0, 105.0, 50.0),
        (105.0, 121.0, 104.0, 120.0, 50.0),
        (120.0, 131.0, 119.0, 130.0, 50.0),
    ]
)


class EnterOnSecondBar(Strategy):
    """Known-answer subject: goes long once two bars are closed."""

    def on_bar(self, history: History) -> float:
        return 1.0 if len(history) >= 2 else 0.0


class Clairvoyant(Strategy):
    """Tries to read the bar AFTER the newest closed one. Must be impossible."""

    def on_bar(self, history: History) -> float:
        future = history[len(history)]  # the engine must make this raise
        return 1.0 if future.close > history.current.close else -1.0


# --- Exit criterion 1: known-answer reproduction ---------------------------


def test_known_answer_fills_and_equity_exact() -> None:
    """Hand-computed: signal at bar1 close (105), fill at bar2 open (105).

    units = 1000/105; equity(bar2) = units*120; equity(bar3) = units*130.
    """
    result = run_backtest(FOUR_BARS, "TEST", EnterOnSecondBar(), config=ZERO_COST)

    (fill,) = result.fills
    assert fill.side == Side.BUY
    assert fill.quantity == pytest.approx(1000.0 / 105.0, rel=1e-12)
    assert fill.price == 105.0  # bar2 open, zero costs
    assert fill.filled_at == FOUR_BARS["timestamp"][2]

    equity = result.equity_curve["equity"].to_list()
    assert equity[0] == 1000.0
    assert equity[1] == 1000.0  # signal placed, nothing filled yet
    assert equity[2] == pytest.approx(1000.0 / 105.0 * 120.0, rel=1e-12)
    assert equity[3] == pytest.approx(1000.0 / 105.0 * 130.0, rel=1e-12)
    assert result.final_equity == pytest.approx(1238.0952380952381, rel=1e-12)


# --- Exit criterion 2: look-ahead is impossible -----------------------------


def test_clairvoyant_strategy_cannot_run() -> None:
    with pytest.raises(IndexError, match="outside closed range"):
        run_backtest(FOUR_BARS, "TEST", Clairvoyant(), config=ZERO_COST)


def test_fills_happen_at_next_bar_open_never_signal_bar() -> None:
    result = run_backtest(FOUR_BARS, "TEST", BuyAndHold(), config=ZERO_COST)
    (fill,) = result.fills
    # Signal on bar0; fill must be bar1's open, at bar1's timestamp.
    assert fill.filled_at == FOUR_BARS["timestamp"][1]
    assert fill.price == FOUR_BARS["open"][1]


# --- Exit criterion 3: buy-and-hold matches manual cost accounting ----------


def test_buy_and_hold_matches_manual_calculation() -> None:
    cfg = BacktestConfig(
        initial_cash=1000.0,
        execution=ExecutionConfig(fee_bps=10.0, half_spread_bps=1.0, impact_bps=25.0),
    )
    result = run_backtest(FOUR_BARS, "TEST", BuyAndHold(), config=cfg)

    # Manual, written independently of broker internals:
    units = 1000.0 / 110.0  # sized at bar0 close
    participation = min(units / 50.0, 1.0)  # bar1 volume
    price = 110.0 * (1 + (1.0 + 25.0 * participation) * 1e-4)  # bar1 open + adverse
    fee = units * price * 10.0 * 1e-4
    expected_final = (1000.0 - units * price - fee) + units * 130.0  # cash + mark at last close

    assert result.final_equity == pytest.approx(expected_final, rel=1e-12)
    assert result.total_fees == pytest.approx(fee, rel=1e-12)


# --- Supporting behavior -----------------------------------------------------


def test_flat_strategy_preserves_cash_exactly() -> None:
    result = run_backtest(FOUR_BARS, "TEST", Flat(), config=ZERO_COST)
    assert result.fills == []
    assert result.equity_curve["equity"].to_list() == [1000.0] * 4
    assert result.final_equity == 1000.0


def test_signal_on_last_bar_is_never_filled() -> None:
    class EnterOnLastBar(Strategy):
        def on_bar(self, history: History) -> float:
            return 1.0 if len(history) == 4 else 0.0

    result = run_backtest(FOUR_BARS, "TEST", EnterOnLastBar(), config=ZERO_COST)
    assert result.fills == []
    assert result.unfilled_orders == 1
    assert result.final_equity == 1000.0


def test_exposure_recorded_after_entry() -> None:
    result = run_backtest(FOUR_BARS, "TEST", EnterOnSecondBar(), config=ZERO_COST)
    exposure = result.equity_curve["exposure"].to_list()
    assert exposure[0] == 0.0
    assert exposure[1] == 0.0
    assert exposure[2] == pytest.approx(1.0)  # fully invested, zero cash drag
    assert exposure[3] == pytest.approx(1.0)


def test_sma_cross_runs_on_longer_series() -> None:
    prices = [100.0 + (i % 20) - (i % 7) + i * 0.05 for i in range(200)]
    frame = make_frame([(p, p + 1, p - 1, p + 0.5, 100.0) for p in prices])
    result = run_backtest(frame, "TEST", SmaCross(fast=5, slow=20), config=ZERO_COST)
    assert result.equity_curve.height == 200
    assert len(result.fills) > 0
    assert result.final_equity > 0


def test_empty_frame_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        run_backtest(FOUR_BARS.head(0), "TEST", Flat())
