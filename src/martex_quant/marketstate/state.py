"""MarketState: the set of observations knowable at an exact timestamp.

The central question this layer answers is "could a trader have known this
at time t?", and the answer has to be enforced by construction rather than
by care. ``History`` already does this for a single instrument in the
backtest engine — it exposes bars only up to a cursor, so indexing into the
future raises. ``MarketState`` is the cross-sectional equivalent: it filters
on an explicit AVAILABILITY time and keeps nothing beyond it.

Availability is not the same as the observation's timestamp
------------------------------------------------------------
A daily bar stamped ``2024-01-01T00:00Z`` describes the 24 hours that follow
it. Nobody knows its close until ``2024-01-02T00:00Z``. So for OHLCV:

    availability_time = bar_timestamp + interval

which is exactly the convention the event-driven engine already encodes as
"decide on the close, fill at the next open". Getting this off by one bar is
the single most common way a backtest lies, which is why the rule is a
declared object here rather than an inline ``<=``.

Scope: OHLCV only, deliberately
-------------------------------
Every other series in the corpus has a genuinely ambiguous availability rule
and NONE is implemented here (see docs/research/mi-layer4-marketstate.md):

* funding rates are stamped at settlement — the stamp IS the availability
  time, not the event time, so the OHLCV rule would be wrong by one cycle;
* open interest is a point-in-time snapshot with no interval at all;
* the derived equity streams are computed from full history, so "the value
  at t" has no meaning independent of how the curve was produced.

Requesting an unsupported kind raises. A rule chosen by convenience would be
worse than no rule: it would make a leaking MarketState look rigorous.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import polars as pl

from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore


class AvailabilityError(Exception):
    """Raised when availability cannot be established, or would be violated."""


@dataclass(frozen=True)
class BarCloseAvailability:
    """OHLCV rule: a bar is knowable once the interval it describes has ended.

    ``lag`` adds an extra delay on top — for a feed that publishes late, or
    to model a deliberately pessimistic assumption. It defaults to zero and
    is recorded on the state so a result can say which assumption produced it.
    """

    interval: Interval
    lag: timedelta = timedelta(0)

    @property
    def name(self) -> str:
        return f"bar_close({self.interval}{f'+{self.lag}' if self.lag else ''})"

    def available_at(self, timestamps: pl.Expr) -> pl.Expr:
        return timestamps + pl.duration(
            milliseconds=self.interval.milliseconds + int(self.lag.total_seconds() * 1000)
        )

    def latest_usable_timestamp(self, as_of: datetime) -> datetime:
        """The newest bar timestamp whose data is knowable by ``as_of``."""
        return as_of - self.interval.duration - self.lag


@dataclass(frozen=True)
class MarketState:
    """Everything knowable at ``as_of``, per symbol. Immutable by construction.

    Frames carry an ``available_at`` column so the guarantee is inspectable
    rather than merely asserted, and every frame has already been filtered —
    there is no accessor that could reach past ``as_of``.
    """

    as_of: datetime
    rule_name: str
    frames: Mapping[str, pl.DataFrame]

    @property
    def symbols(self) -> list[str]:
        return sorted(self.frames)

    def frame(self, symbol: str) -> pl.DataFrame:
        if symbol not in self.frames:
            raise KeyError(f"{symbol} is not in this state (as of {self.as_of})")
        return self.frames[symbol]

    def latest(self, symbol: str, column: str) -> float | None:
        """Newest knowable value, or None when nothing is available yet."""
        frame = self.frame(symbol)
        if frame.height == 0:
            return None
        value = frame[column][-1]
        return float(value) if isinstance(value, int | float) else None

    def cross_section(self, column: str) -> dict[str, float]:
        """The column's newest knowable value for every symbol that has one."""
        out: dict[str, float] = {}
        for symbol in self.symbols:
            value = self.latest(symbol, column)
            if value is not None:
                out[symbol] = value
        return out

    def max_available_at(self) -> datetime | None:
        """The latest availability time anywhere in the state — the number a
        leak check compares against ``as_of``."""
        stamps = [
            frame["available_at"][-1]
            for frame in self.frames.values()
            if frame.height > 0 and "available_at" in frame.columns
        ]
        return max(stamps) if stamps else None


class MarketStateEngine:
    """Builds MarketState objects from the lake under an availability rule."""

    def __init__(self, store: ParquetStore, rule: BarCloseAvailability) -> None:
        self.store = store
        self.rule = rule

    def as_of(self, timestamp: datetime, symbols: Sequence[str]) -> MarketState:
        """State at ``timestamp``, containing only what was knowable by then.

        A symbol with no usable history yet appears with an empty frame
        rather than being dropped: "listed but not yet observable" and "not
        in the universe" are different facts, and collapsing them is how
        survivorship creeps in.
        """
        if timestamp.tzinfo is None:
            raise AvailabilityError("as_of must be timezone-aware; the corpus is UTC throughout")

        frames: dict[str, pl.DataFrame] = {}
        for symbol in symbols:
            try:
                frame = self.store.read(symbol, self.rule.interval)
            except FileNotFoundError:
                continue  # absent from the lake entirely, not merely unobservable
            frame = frame.with_columns(
                self.rule.available_at(pl.col("timestamp")).alias("available_at")
            )
            frames[symbol] = frame.filter(pl.col("available_at") <= timestamp)
        return MarketState(as_of=timestamp, rule_name=self.rule.name, frames=frames)


def assert_no_lookahead(state: MarketState) -> None:
    """Fail loudly if any observation in the state postdates its as_of.

    The poison tests drive this: a state built with a wrong rule, or from a
    frame carrying future rows, trips here. Kept as a standalone function so
    it can also guard callers that build states by other means.
    """
    latest = state.max_available_at()
    if latest is not None and latest > state.as_of:
        raise AvailabilityError(
            f"look-ahead: state as of {state.as_of} contains data available only at {latest} "
            f"(rule {state.rule_name})"
        )
    for symbol, frame in state.frames.items():
        if "available_at" not in frame.columns:
            raise AvailabilityError(f"{symbol}: frame has no availability column to verify")
        if frame.height and frame["available_at"].max() > state.as_of:  # type: ignore[operator]
            raise AvailabilityError(f"{symbol}: contains data unavailable at {state.as_of}")
