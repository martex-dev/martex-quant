"""Simulated broker tests: cost model math, hand-computed."""

from datetime import UTC, datetime

import pytest

from martex_quant.core.events import Bar, Order, Side
from martex_quant.execution.simulated import ExecutionConfig, SimulatedBroker

TS = datetime(2024, 1, 1, tzinfo=UTC)
BAR = Bar(TS, open=200.0, high=210.0, low=190.0, close=205.0, volume=100.0)


def make_order(side: Side, quantity: float) -> Order:
    return Order(created_at=TS, symbol="BTCUSDT", side=side, quantity=quantity)


def test_buy_fill_price_and_fee_hand_computed() -> None:
    broker = SimulatedBroker(ExecutionConfig(fee_bps=10.0, half_spread_bps=1.0, impact_bps=25.0))
    broker.submit(make_order(Side.BUY, 2.0))
    (fill,) = broker.execute_pending(BAR)

    # participation = 2/100 = 0.02 -> adverse = 1 + 25*0.02 = 1.5 bps
    assert fill.price == pytest.approx(200.0 * (1 + 1.5e-4))
    assert fill.fee == pytest.approx(2.0 * fill.price * 10e-4)
    assert fill.filled_at == TS
    assert fill.signed_quantity == 2.0


def test_sell_fill_is_adjusted_downward() -> None:
    broker = SimulatedBroker(ExecutionConfig(fee_bps=0.0, half_spread_bps=2.0, impact_bps=0.0))
    broker.submit(make_order(Side.SELL, 1.0))
    (fill,) = broker.execute_pending(BAR)
    assert fill.price == pytest.approx(200.0 * (1 - 2e-4))
    assert fill.signed_quantity == -1.0


def test_zero_cost_config_fills_at_open_exactly() -> None:
    broker = SimulatedBroker(ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=0.0))
    broker.submit(make_order(Side.BUY, 5.0))
    (fill,) = broker.execute_pending(BAR)
    assert fill.price == 200.0
    assert fill.fee == 0.0


def test_zero_volume_bar_charges_full_participation() -> None:
    broker = SimulatedBroker(ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=25.0))
    broker.submit(make_order(Side.BUY, 1.0))
    dead_bar = Bar(TS, 200.0, 200.0, 200.0, 200.0, volume=0.0)
    (fill,) = broker.execute_pending(dead_bar)
    assert fill.price == pytest.approx(200.0 * (1 + 25e-4))


def test_participation_capped_at_full_volume() -> None:
    broker = SimulatedBroker(ExecutionConfig(fee_bps=0.0, half_spread_bps=0.0, impact_bps=25.0))
    broker.submit(make_order(Side.BUY, 500.0))  # 5x the bar's volume
    (fill,) = broker.execute_pending(BAR)
    assert fill.price == pytest.approx(200.0 * (1 + 25e-4))  # capped, not 125 bps


def test_pending_cleared_after_execution() -> None:
    broker = SimulatedBroker()
    broker.submit(make_order(Side.BUY, 1.0))
    assert len(broker.pending) == 1
    broker.execute_pending(BAR)
    assert broker.pending == []
    assert broker.execute_pending(BAR) == []
