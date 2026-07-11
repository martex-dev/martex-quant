"""Canonical data schemas shared across the data subsystem.

Every collector must produce, and every consumer may assume, exactly the
schema defined here. Symbol and interval are not columns: they live in the
partition path and the catalog.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

import polars as pl


class Interval(StrEnum):
    """Supported bar intervals, spelled the way exchanges spell them."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    H6 = "6h"
    H12 = "12h"
    D1 = "1d"

    @property
    def duration(self) -> timedelta:
        return _DURATIONS[self]

    @property
    def milliseconds(self) -> int:
        return int(self.duration.total_seconds() * 1000)


_DURATIONS: dict[Interval, timedelta] = {
    Interval.M1: timedelta(minutes=1),
    Interval.M5: timedelta(minutes=5),
    Interval.M15: timedelta(minutes=15),
    Interval.H1: timedelta(hours=1),
    Interval.H4: timedelta(hours=4),
    Interval.H6: timedelta(hours=6),
    Interval.H12: timedelta(hours=12),
    Interval.D1: timedelta(days=1),
}

# Bar open time, always UTC, millisecond precision (exchange-native).
TIMESTAMP_DTYPE = pl.Datetime(time_unit="ms", time_zone="UTC")

OHLCV_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")

OHLCV_SCHEMA: dict[str, pl.DataType] = {
    "timestamp": TIMESTAMP_DTYPE,
    "open": pl.Float64(),
    "high": pl.Float64(),
    "low": pl.Float64(),
    "close": pl.Float64(),
    "volume": pl.Float64(),
}


def ohlcv_frame_from_rows(rows: list[list[float]]) -> pl.DataFrame:
    """Build a canonical OHLCV frame from exchange rows.

    ``rows`` are ``[timestamp_ms, open, high, low, close, volume]`` — the
    shape ccxt returns from ``fetch_ohlcv``.
    """
    if not rows:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    df = pl.DataFrame(
        {
            "timestamp": [int(r[0]) for r in rows],
            "open": [float(r[1]) for r in rows],
            "high": [float(r[2]) for r in rows],
            "low": [float(r[3]) for r in rows],
            "close": [float(r[4]) for r in rows],
            "volume": [float(r[5]) for r in rows],
        }
    )
    return df.with_columns(
        pl.from_epoch("timestamp", time_unit="ms").dt.replace_time_zone("UTC").cast(TIMESTAMP_DTYPE)
    )
