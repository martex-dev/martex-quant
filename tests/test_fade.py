"""Unit tests for the H51 intraday fade strategies."""

from datetime import UTC, datetime, timedelta

from martex_quant.backtesting.history import History
from martex_quant.core.events import Bar
from martex_quant.strategies.fade import FadeFirstHour, FadeORB

DAY0 = datetime(2024, 1, 1, tzinfo=UTC)


def make_day(base: float, closes_by_slot: dict[int, float]) -> list[Bar]:
    """96 bars of a flat day at ``base``, with specific 15m slots overridden."""
    bars = []
    for i in range(96):
        c = closes_by_slot.get(i, base)
        bars.append(Bar(DAY0 + timedelta(minutes=15 * i), c, c * 1.001, c * 0.999, c, 100.0))
    return bars


def run(strategy, bars):  # noqa: ANN001, ANN201
    history = History(bars)
    exposures = []
    for _ in bars:
        history.advance()
        exposures.append(strategy.on_bar(history))
    return exposures


def test_fade_orb_shorts_an_upside_break_and_flattens() -> None:
    # First hour ~100; bar 8 (02:00) closes well above the range -> short.
    bars = make_day(100.0, {8: 103.0})
    exposures = run(FadeORB(), bars)
    assert exposures[7] == 0.0
    assert exposures[8] == -1.0  # faded the break
    assert all(e == -1.0 for e in exposures[9:95])
    assert exposures[95] == 0.0  # flat into the day close


def test_fade_orb_longs_a_downside_break_once_only() -> None:
    bars = make_day(100.0, {6: 97.0, 10: 94.0})
    exposures = run(FadeORB(), bars)
    assert exposures[6] == 1.0
    assert exposures[10] == 1.0  # second break does not re-enter/flip


def test_fade_orb_no_break_no_position() -> None:
    exposures = run(FadeORB(), make_day(100.0, {}))
    assert all(e == 0.0 for e in exposures)


def test_fade_first_hour_shorts_up_move() -> None:
    # First hour rises 100 -> 102: fade short from the 00:45 decision.
    bars = make_day(100.0, {0: 100.0, 1: 101.0, 2: 101.5, 3: 102.0})
    exposures = run(FadeFirstHour(), bars)
    assert exposures[2] == 0.0
    assert exposures[3] == -1.0
    assert exposures[94] == -1.0
    assert exposures[95] == 0.0


def test_fade_first_hour_flat_when_first_hour_flat() -> None:
    exposures = run(FadeFirstHour(), make_day(100.0, {}))
    # open == close on every bar -> r0 == 0 -> no trade
    assert all(e == 0.0 for e in exposures)
