"""Point-in-time universe selection.

`config/universe.json` fixes its 40 symbols by "top40 by 24h quote
volume, **2026-07-12**" -- a snapshot taken at the end of the research
sample. Ranking a 2018-2026 backtest inside that set means ranking among
coins that are present *because* they later became prominent.

This module builds the universe a selector could actually have had: at
each reselection date, the top N by trailing quote volume among symbols
that already had enough history.

Spec: docs/hypotheses/71-point-in-time-universe.md Section 4.2.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class UniverseSchedule:
    """Which symbols were selectable from which date.

    ``entries`` is sorted by date. ``for_date`` returns the universe in
    force on a given day: the most recent selection at or before it, so a
    lookup can never see a future reselection.
    """

    entries: tuple[tuple[dt.date, frozenset[str]], ...]

    def for_date(self, day: dt.date) -> frozenset[str]:
        chosen: frozenset[str] = frozenset()
        for when, symbols in self.entries:
            if when > day:
                break
            chosen = symbols
        return chosen

    @property
    def turnover(self) -> list[int]:
        """Symbols added at each reselection after the first."""
        return [
            len(curr - prev)
            for (_, prev), (_, curr) in zip(self.entries, self.entries[1:], strict=False)
        ]


def point_in_time_universes(
    frames: dict[str, pl.DataFrame],
    *,
    size: int,
    volume_window: int,
    min_history: int,
    reselect_every: int,
    start: dt.datetime,
    end: dt.datetime,
) -> UniverseSchedule:
    """Top ``size`` symbols by trailing mean quote volume, reselected periodically.

    Every input to a selection is dated at or before the selection day, so
    the schedule contains no look-ahead. A symbol must already carry
    ``min_history`` bars to be eligible, which is what stops the selector
    from buying a coin that listed yesterday.
    """
    volume: dict[str, pl.DataFrame] = {}
    for symbol, frame in frames.items():
        if "quote_volume" not in frame.columns:
            continue
        volume[symbol] = frame.select("timestamp", "quote_volume").sort("timestamp")

    entries: list[tuple[dt.date, frozenset[str]]] = []
    when = start
    while when <= end:
        scored: list[tuple[float, str]] = []
        for symbol, frame in volume.items():
            history = frame.filter(pl.col("timestamp") <= when)
            if history.height < min_history:
                continue
            # polars' mean() is typed as a union over every dtype it could
            # hold, so narrow once rather than fighting it per comparison.
            mean = history.tail(volume_window)["quote_volume"].mean()
            if mean is None:
                continue
            turnover = float(mean)  # type: ignore[arg-type]
            if turnover <= 0.0:
                continue
            scored.append((turnover, symbol))
        scored.sort(reverse=True)
        if scored:
            entries.append((when.date(), frozenset(s for _, s in scored[:size])))
        when += dt.timedelta(days=reselect_every)

    return UniverseSchedule(entries=tuple(entries))
