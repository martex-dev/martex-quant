"""Unit tests for point-in-time universe selection (H71).

The property that matters is NO LOOK-AHEAD. The whole hypothesis is that
the deployed universe was chosen with information from the end of the
sample; a selector that leaked future volume would reproduce the very
defect it exists to measure, and would do it invisibly.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from martex_quant.backtesting.history import History
from martex_quant.backtesting.multi import MultiAssetStrategy
from martex_quant.core.events import Bar
from martex_quant.features.universe import UniverseSchedule, point_in_time_universes
from martex_quant.strategies.masked import UniverseMasked

START = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)


def _frame(days: int, volume: float, *, offset: int = 0) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [START + dt.timedelta(days=offset + i) for i in range(days)],
            "quote_volume": [volume] * days,
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("us", "UTC")))


def _select(frames: dict[str, pl.DataFrame], **kwargs: object) -> UniverseSchedule:
    defaults: dict[str, object] = {
        "size": 2,
        "volume_window": 30,
        "min_history": 90,
        "reselect_every": 90,
        "start": START + dt.timedelta(days=100),
        "end": START + dt.timedelta(days=200),
    }
    defaults.update(kwargs)
    return point_in_time_universes(frames, **defaults)  # type: ignore[arg-type]


def test_it_picks_the_highest_volume_symbols() -> None:
    schedule = _select(
        {"BIG": _frame(300, 1_000.0), "MID": _frame(300, 500.0), "SMALL": _frame(300, 1.0)}
    )
    assert schedule.entries
    assert schedule.entries[0][1] == frozenset({"BIG", "MID"})


def test_a_symbol_without_enough_history_is_not_selectable() -> None:
    """MIN_HISTORY is what stops the selector buying yesterday's listing."""
    schedule = _select(
        {
            "OLD": _frame(300, 10.0),
            "NEW": _frame(300, 1_000_000.0, offset=95),  # huge, but too young
        }
    )
    assert schedule.entries[0][1] == frozenset({"OLD"})


def test_future_volume_cannot_influence_an_earlier_selection() -> None:
    """The load-bearing test: a coin that becomes enormous LATER must not
    be selected earlier. This is precisely the defect H71 measures."""
    quiet_then_huge = pl.concat([_frame(150, 1.0), _frame(150, 1_000_000.0, offset=150)])
    schedule = _select(
        {"STEADY": _frame(300, 100.0), "LATE": quiet_then_huge},
        start=START + dt.timedelta(days=100),
        end=START + dt.timedelta(days=100),
        size=1,
    )
    assert schedule.entries[0][1] == frozenset({"STEADY"})


def test_the_same_symbol_is_selected_once_it_actually_is_large() -> None:
    quiet_then_huge = pl.concat([_frame(150, 1.0), _frame(150, 1_000_000.0, offset=150)])
    schedule = _select(
        {"STEADY": _frame(300, 100.0), "LATE": quiet_then_huge},
        start=START + dt.timedelta(days=250),
        end=START + dt.timedelta(days=250),
        size=1,
    )
    assert schedule.entries[0][1] == frozenset({"LATE"})


def test_for_date_never_returns_a_future_selection() -> None:
    schedule = UniverseSchedule(
        entries=(
            (dt.date(2020, 1, 1), frozenset({"A"})),
            (dt.date(2021, 1, 1), frozenset({"B"})),
        )
    )
    assert schedule.for_date(dt.date(2020, 6, 1)) == frozenset({"A"})
    assert schedule.for_date(dt.date(2021, 6, 1)) == frozenset({"B"})
    assert schedule.for_date(dt.date(2019, 6, 1)) == frozenset()


def test_turnover_counts_names_added() -> None:
    schedule = UniverseSchedule(
        entries=(
            (dt.date(2020, 1, 1), frozenset({"A", "B"})),
            (dt.date(2020, 4, 1), frozenset({"B", "C"})),
        )
    )
    assert schedule.turnover == [1]


# --- the masking wrapper -------------------------------------------------


class _RecordingStrategy(MultiAssetStrategy):
    def __init__(self) -> None:
        self.seen: set[str] = set()

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        self.seen = set(histories)
        return dict.fromkeys(histories, 1.0 / len(histories)) if histories else {}


def _history(end: dt.datetime, days: int = 5) -> History:
    bars = [
        Bar(
            timestamp=end - dt.timedelta(days=days - 1 - i),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1.0,
        )
        for i in range(days)
    ]
    history = History(bars)
    for _ in range(days):
        history.advance()
    return history


def test_the_mask_hides_symbols_outside_the_days_universe() -> None:
    day = dt.datetime(2020, 6, 1, tzinfo=dt.UTC)
    schedule = UniverseSchedule(entries=((dt.date(2020, 1, 1), frozenset({"IN"})),))
    inner = _RecordingStrategy()
    weights = UniverseMasked(inner, schedule).target_weights(
        {"IN": _history(day), "OUT": _history(day)}
    )
    assert inner.seen == {"IN"}
    assert weights == pytest.approx({"IN": 1.0})


def test_an_empty_universe_means_cash_not_a_crash() -> None:
    day = dt.datetime(2019, 6, 1, tzinfo=dt.UTC)
    schedule = UniverseSchedule(entries=((dt.date(2020, 1, 1), frozenset({"IN"})),))
    assert (
        UniverseMasked(_RecordingStrategy(), schedule).target_weights({"IN": _history(day)}) == {}
    )
