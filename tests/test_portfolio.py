"""Portfolio tests: exposure translation and ledger accounting."""

from datetime import UTC, datetime

import pytest

from martex_quant.core.events import Bar, Fill, Side
from martex_quant.portfolio.portfolio import Portfolio

TS = datetime(2024, 1, 1, tzinfo=UTC)
BAR = Bar(TS, open=100.0, high=101.0, low=99.0, close=100.0, volume=50.0)


def test_full_long_order_sized_off_equity() -> None:
    portfolio = Portfolio("BTCUSDT", initial_cash=1000.0)
    order = portfolio.target_order(1.0, BAR)
    assert order is not None
    assert order.side == Side.BUY
    assert order.quantity == pytest.approx(10.0)  # 1000 / 100


def test_no_order_when_target_unchanged() -> None:
    portfolio = Portfolio("BTCUSDT", initial_cash=1000.0)
    assert portfolio.target_order(1.0, BAR) is not None
    assert portfolio.target_order(1.0, BAR) is None  # same target, no churn


def test_flat_target_from_start_produces_no_order() -> None:
    portfolio = Portfolio("BTCUSDT", initial_cash=1000.0)
    assert portfolio.target_order(0.0, BAR) is None


def test_short_clamped_to_flat_when_shorting_disabled() -> None:
    portfolio = Portfolio("BTCUSDT", initial_cash=1000.0, allow_short=False)
    assert portfolio.target_order(-1.0, BAR) is None  # clamped to 0 == start


def test_short_allowed_when_enabled() -> None:
    portfolio = Portfolio("BTCUSDT", initial_cash=1000.0, allow_short=True)
    order = portfolio.target_order(-1.0, BAR)
    assert order is not None
    assert order.side == Side.SELL
    assert order.quantity == pytest.approx(10.0)


def test_apply_fill_updates_cash_and_position() -> None:
    portfolio = Portfolio("BTCUSDT", initial_cash=1000.0)
    portfolio.apply_fill(
        Fill(filled_at=TS, symbol="BTCUSDT", side=Side.BUY, quantity=5.0, price=100.0, fee=0.5)
    )
    assert portfolio.position == 5.0
    assert portfolio.cash == pytest.approx(1000.0 - 500.0 - 0.5)
    assert portfolio.equity(price=110.0) == pytest.approx(499.5 + 550.0)

    portfolio.apply_fill(
        Fill(filled_at=TS, symbol="BTCUSDT", side=Side.SELL, quantity=5.0, price=110.0, fee=0.55)
    )
    assert portfolio.position == 0.0
    assert portfolio.cash == pytest.approx(1000.0 - 500.0 - 0.5 + 550.0 - 0.55)


def test_exposure_change_orders_the_delta_only() -> None:
    portfolio = Portfolio("BTCUSDT", initial_cash=1000.0)
    first = portfolio.target_order(1.0, BAR)
    assert first is not None
    portfolio.apply_fill(
        Fill(TS, "BTCUSDT", Side.BUY, quantity=first.quantity, price=100.0, fee=0.0)
    )
    # Halve the exposure: should sell roughly half the position, not rebuild.
    order = portfolio.target_order(0.5, BAR)
    assert order is not None
    assert order.side == Side.SELL
    assert order.quantity == pytest.approx(5.0)


def test_invalid_initial_cash_rejected() -> None:
    with pytest.raises(ValueError):
        Portfolio("BTCUSDT", initial_cash=0.0)
