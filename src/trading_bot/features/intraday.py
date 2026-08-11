"""Intraday 15-minute bar loading.

Consolidates the identical ``load`` helper that h44_50 and h52_55_57 each
carried. The intraday caches are raw parquet outside the lake — they have
their own column name (``ts``, not ``timestamp``) and no catalog entry —
which is why this reads files directly rather than going through
``ParquetStore``. That gap is recorded as a Layer 3 concern, not fixed here.

Deliberately NOT consolidated:

* ``h53_killtest`` reads the ``_tb15m`` taker-buy panels, a different dataset
  with a different schema, and derives only ``day``.
* ``h51_fade_study`` renames ``ts`` to ``timestamp`` because it feeds the
  event-driven backtest engine, which requires the canonical column name.
  Same file, different contract.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl


def load_15m_bars(data_dir: Path, symbol: str) -> pl.DataFrame:
    """Load one symbol's 15m OHLCV cache with calendar/clock columns derived.

    Sorted by ``ts`` on load — the caches are written sorted, but the
    downstream per-day grouping and every rolling window depend on it, so it
    is asserted rather than trusted.

    ``day`` is a DATE (not a datetime): the intraday studies pool events by
    calendar day for the day-block bootstrap. ``hh``/``mm`` drive the
    session and opening-range logic.
    """
    return (
        pl.read_parquet(data_dir / f"{symbol}_15m.parquet")
        .sort("ts")
        .with_columns(
            day=pl.col("ts").dt.date(),
            hh=pl.col("ts").dt.hour(),
            mm=pl.col("ts").dt.minute(),
        )
    )
