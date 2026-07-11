"""OHLCV resampling: build coarser bars from finer ones (1h -> 6h/12h).

Buckets are epoch-aligned (matching how Binance aligns its own 6h/12h
klines) and INCOMPLETE BUCKETS ARE DROPPED — a 6h bar built from four
1h bars would silently misstate high/low/volume, so it is not emitted.
"""

from __future__ import annotations

import polars as pl

from trading_bot.data.models import OHLCV_SCHEMA, TIMESTAMP_DTYPE, Interval


def resample_ohlcv(df: pl.DataFrame, source: Interval, target: Interval) -> pl.DataFrame:
    """Aggregate canonical ``source``-interval bars into ``target`` bars."""
    if dict(df.schema) != OHLCV_SCHEMA:
        raise ValueError("input frame does not match canonical OHLCV schema")
    if target.milliseconds % source.milliseconds != 0 or target.milliseconds <= source.milliseconds:
        raise ValueError(f"target {target} must be a coarser multiple of source {source}")
    factor = target.milliseconds // source.milliseconds

    bucket = (
        (pl.col("timestamp").cast(pl.Int64) // target.milliseconds) * target.milliseconds
    ).alias("bucket")
    out = (
        df.sort("timestamp")
        .with_columns(bucket)
        .group_by("bucket", maintain_order=True)
        .agg(
            open=pl.col("open").first(),
            high=pl.col("high").max(),
            low=pl.col("low").min(),
            close=pl.col("close").last(),
            volume=pl.col("volume").sum(),
            n=pl.len(),
        )
        .filter(pl.col("n") == factor)  # complete buckets only
        .drop("n")
        .with_columns(pl.from_epoch("bucket", time_unit="ms").cast(TIMESTAMP_DTYPE))
        .rename({"bucket": "timestamp"})
        .select(list(OHLCV_SCHEMA))
    )
    return out
