"""Unit tests for the H69 cross-venue ladder.

The weights contract is the whole safety property here: the engine raises
if weights are negative or sum above 1, and a ladder that silently
over-allocates would look like a leveraged book that was never approved.
"""

from __future__ import annotations

import datetime as dt

import pytest

from martex_quant.backtesting.history import History
from martex_quant.core.events import Bar
from martex_quant.strategies.crossvenue import CrossVenuePremiumLadder, EqualWeightBuyAndHold

DAY = dt.datetime(2024, 3, 10, tzinfo=dt.UTC)


def _history(days: int, end: dt.datetime = DAY) -> History:
    """Bar is a plain OHLCV NamedTuple; the symbol lives in the dict key."""
    bars = [
        Bar(
            timestamp=end - dt.timedelta(days=days - 1 - i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
        for i in range(days)
    ]
    history = History(bars)
    for _ in range(days):
        history.advance()
    return history


def _histories(*symbols: str, days: int = 40) -> dict[str, History]:
    return {s: _history(days) for s in symbols}


def test_no_qualifiers_means_fully_in_cash() -> None:
    strategy = CrossVenuePremiumLadder({}, hold=7)
    assert strategy.target_weights(_histories("BTC", "ETH")) == {}


def test_a_single_tranche_holds_one_seventh_of_capital() -> None:
    strategy = CrossVenuePremiumLadder({DAY.date(): ("BTC",)}, hold=7)
    weights = strategy.target_weights(_histories("BTC", "ETH"))
    assert weights == pytest.approx({"BTC": 1.0 / 7.0})


def test_a_tranche_splits_equally_across_its_qualifiers() -> None:
    strategy = CrossVenuePremiumLadder({DAY.date(): ("BTC", "ETH")}, hold=7)
    weights = strategy.target_weights(_histories("BTC", "ETH"))
    assert weights == pytest.approx({"BTC": 1.0 / 14.0, "ETH": 1.0 / 14.0})


def test_weights_never_exceed_one_when_every_tranche_is_live() -> None:
    """The engine rejects sum > 1; a full ladder must land exactly at 1."""
    qualifiers = {DAY.date() - dt.timedelta(days=age): ("BTC",) for age in range(7)}
    strategy = CrossVenuePremiumLadder(qualifiers, hold=7)
    weights = strategy.target_weights(_histories("BTC"))
    assert weights["BTC"] == pytest.approx(1.0)
    assert sum(weights.values()) <= 1.0 + 1e-9


def test_tranches_older_than_the_holding_period_have_rolled_off() -> None:
    qualifiers = {DAY.date() - dt.timedelta(days=7): ("BTC",)}
    strategy = CrossVenuePremiumLadder(qualifiers, hold=7)
    assert strategy.target_weights(_histories("BTC")) == {}


def test_a_symbol_that_did_not_trade_today_is_not_sized_off_a_stale_print() -> None:
    """XRP's Coinbase halt is the real case: a name can vanish mid-hold."""
    histories = {
        "BTC": _history(40),
        "XRP": _history(40, end=DAY - dt.timedelta(days=5)),
    }
    strategy = CrossVenuePremiumLadder({DAY.date(): ("BTC", "XRP")}, hold=7)
    weights = strategy.target_weights(histories)
    # XRP is dropped, and BTC keeps the weight it was given on the entry
    # day rather than inheriting XRP's half.
    assert weights == pytest.approx({"BTC": 1.0 / 14.0})


def test_buy_and_hold_equal_weights_only_symbols_trading_today() -> None:
    histories = {
        "BTC": _history(40),
        "XRP": _history(40, end=DAY - dt.timedelta(days=5)),
    }
    assert EqualWeightBuyAndHold().target_weights(histories) == pytest.approx({"BTC": 1.0})


def test_hold_must_be_positive() -> None:
    with pytest.raises(ValueError):
        CrossVenuePremiumLadder({}, hold=0)
