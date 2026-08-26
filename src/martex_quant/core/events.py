"""Event types flowing through the trading system.

The backtest engine and the future live engine speak exactly this vocabulary;
strategies and portfolio/risk code never see anything richer. A "signal" is
currently just the float target exposure a strategy returns — it gets its own
event type when live routing needs metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NamedTuple

import polars as pl


class Bar(NamedTuple):
    """One closed OHLCV bar. ``timestamp`` is the bar OPEN time (UTC)."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Order:
    """A market order. ``quantity`` is in base units and always positive."""

    created_at: datetime
    symbol: str
    side: Side
    quantity: float


@dataclass(frozen=True, slots=True)
class Fill:
    """An executed order. ``price`` includes spread and slippage; ``fee`` is
    in quote currency."""

    filled_at: datetime
    symbol: str
    side: Side
    quantity: float
    price: float
    fee: float

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side == Side.BUY else -self.quantity


def bars_from_frame(df: pl.DataFrame) -> list[Bar]:
    """Convert a canonical OHLCV frame into Bar tuples for the event loop."""
    return [Bar(*row) for row in df.iter_rows()]
