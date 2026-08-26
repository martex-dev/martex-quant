"""Investable market indices built from the lake — the V2 dominance
signal's foundation (docs/research/v2-dominance-rotation-phase0.md).

Equal-weight, daily-chained, LISTING-AWARE: a symbol contributes from
its first bar onward; on days it has no return (entry day, missing bar)
the mean simply excludes it. External aggregates like TradingView BTC.D
are deliberately not used (stablecoin/dead-coin pollution).
"""

from __future__ import annotations

import polars as pl

from martex_quant.data.models import TIMESTAMP_DTYPE


def equal_weight_index(frames: dict[str, pl.DataFrame], base: float = 100.0) -> pl.DataFrame:
    """Chained equal-weight index of the given symbols' closes.

    Returns (timestamp, level). Index return on day t = mean of the
    daily returns of all symbols that HAVE a return on day t.
    """
    if not frames:
        raise ValueError("need at least one symbol")
    wide: pl.DataFrame | None = None
    for symbol, df in frames.items():
        part = df.select(pl.col("timestamp").cast(TIMESTAMP_DTYPE), pl.col("close").alias(symbol))
        wide = part if wide is None else wide.join(part, on="timestamp", how="full", coalesce=True)
    assert wide is not None
    wide = wide.sort("timestamp")

    symbols = list(frames)
    returns = wide.with_columns(
        [(pl.col(s) / pl.col(s).shift(1) - 1.0).alias(s) for s in symbols]
    ).with_columns(pl.mean_horizontal([pl.col(s) for s in symbols]).alias("ret"))

    levels = returns.select(
        "timestamp",
        ((1.0 + pl.col("ret").fill_null(0.0)).cum_prod() * base).alias("level"),
    )
    return levels


def dominance_series(btc: pl.DataFrame, alt_index: pl.DataFrame) -> pl.DataFrame:
    """Dominance proxy: BTC close / alt-index level, joined on timestamp.

    Rising values = BTC outperforming the investable alt basket. Same
    economic content as 'BTC dominance', none of the aggregate-cap mess.
    """
    joined = btc.select(pl.col("timestamp").cast(TIMESTAMP_DTYPE), pl.col("close")).join(
        alt_index, on="timestamp", how="inner"
    )
    return joined.select("timestamp", (pl.col("close") / pl.col("level")).alias("dominance")).sort(
        "timestamp"
    )
