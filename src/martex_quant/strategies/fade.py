"""Intraday fade strategies. Spec: docs/hypotheses/51-intraday-fade.md.

15m bars, UTC day sessions. Both fade the crowd's favorite entries:
H44/H45 measured the breakout side losing 0.16-0.20% per event.
Engine semantics give the registered fills for free: a signal at bar
t's close fills at bar t+1's open (entry), and the 23:45 exit signal
fills at the next day's 00:00 open (~the day close).
"""

from __future__ import annotations

from datetime import date

from martex_quant.backtesting.history import History
from martex_quant.strategies.base import Strategy

_LAST_BAR = (23, 45)


class _DaySession:
    """Tracks the current UTC day's first-hour range and entry state."""

    def __init__(self) -> None:
        self.day: date | None = None
        self.range_high: float | None = None
        self.range_low: float | None = None
        self.first_open: float | None = None
        self.first_hour_bars = 0
        self.entered = False

    def roll(self, bar_day: date) -> None:
        if bar_day != self.day:
            self.day = bar_day
            self.range_high = None
            self.range_low = None
            self.first_open = None
            self.first_hour_bars = 0
            self.entered = False


class FadeORB(Strategy):
    """51a: on the first 15m close beyond the first hour's range within
    hours 1-5, take the OPPOSITE side; flat into the day close."""

    def __init__(self) -> None:
        self._session = _DaySession()
        self._exposure = 0.0

    def warmup(self) -> int:
        return 1

    def on_bar(self, history: History) -> float:
        bar = history.current
        ts = bar.timestamp
        session = self._session
        session.roll(ts.date())

        if (ts.hour, ts.minute) == _LAST_BAR:
            self._exposure = 0.0
            return self._exposure

        if ts.hour == 0:
            session.range_high = (
                bar.high if session.range_high is None else max(session.range_high, bar.high)
            )
            session.range_low = (
                bar.low if session.range_low is None else min(session.range_low, bar.low)
            )
            session.first_hour_bars += 1
            return self._exposure

        if (
            not session.entered
            and session.first_hour_bars == 4
            and session.range_high is not None
            and session.range_low is not None
            and 1 <= ts.hour <= 5
        ):
            if bar.close > session.range_high:
                session.entered = True
                self._exposure = -1.0
            elif bar.close < session.range_low:
                session.entered = True
                self._exposure = 1.0
        return self._exposure


class FadeFirstHour(Strategy):
    """51b: at 01:00 UTC take the OPPOSITE side of the 00:00-01:00 move;
    flat into the day close."""

    def __init__(self) -> None:
        self._session = _DaySession()
        self._exposure = 0.0

    def warmup(self) -> int:
        return 1

    def on_bar(self, history: History) -> float:
        bar = history.current
        ts = bar.timestamp
        session = self._session
        session.roll(ts.date())

        if (ts.hour, ts.minute) == _LAST_BAR:
            self._exposure = 0.0
            return self._exposure

        if ts.hour == 0:
            if session.first_open is None:
                session.first_open = bar.open
            session.first_hour_bars += 1
            if session.first_hour_bars == 4 and not session.entered:
                # Decision at the 00:45 bar's close -> fills at 01:00 open.
                session.entered = True
                r0 = bar.close / session.first_open - 1.0 if session.first_open else 0.0
                if r0 > 0:
                    self._exposure = -1.0
                elif r0 < 0:
                    self._exposure = 1.0
        return self._exposure
