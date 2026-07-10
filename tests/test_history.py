"""History view tests: the look-ahead firewall."""

from datetime import UTC, datetime, timedelta

import pytest

from trading_bot.backtesting.history import History
from trading_bot.core.events import Bar

START = datetime(2024, 1, 1, tzinfo=UTC)


def make_bars(n: int) -> list[Bar]:
    return [
        Bar(START + timedelta(hours=i), 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0)
        for i in range(n)
    ]


def test_starts_empty() -> None:
    history = History(make_bars(5))
    assert len(history) == 0
    with pytest.raises(IndexError):
        _ = history.current


def test_advance_exposes_exactly_one_more_bar() -> None:
    bars = make_bars(5)
    history = History(bars)
    for i in range(5):
        history.advance()
        assert len(history) == i + 1
        assert history.current == bars[i]


def test_future_bars_are_unreachable() -> None:
    history = History(make_bars(5))
    history.advance()  # only bar 0 is closed
    with pytest.raises(IndexError):
        _ = history[1]  # bar 1 exists in the data but is the future
    with pytest.raises(IndexError):
        _ = history[len(history)]


def test_negative_index_counts_from_newest_closed() -> None:
    bars = make_bars(5)
    history = History(bars)
    history.advance()
    history.advance()
    assert history[-1] == bars[1]
    assert history[-2] == bars[0]
    with pytest.raises(IndexError):
        _ = history[-3]


def test_window_clips_at_start_and_never_reaches_future() -> None:
    bars = make_bars(5)
    history = History(bars)
    history.advance()
    history.advance()
    assert list(history.window(10)) == bars[:2]
    assert list(history.window(1)) == [bars[1]]
    assert history.closes(2) == [bars[0].close, bars[1].close]
    with pytest.raises(ValueError):
        history.window(0)


def test_cannot_advance_past_end() -> None:
    history = History(make_bars(2))
    history.advance()
    history.advance()
    with pytest.raises(IndexError):
        history.advance()
