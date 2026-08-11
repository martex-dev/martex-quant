"""Hypothesis 08 kill test: funding extremes vs forward spot returns.

    .venv/Scripts/python scripts/h08_funding_killtest.py

Spec pre-registered in docs/hypotheses/08-funding-extremes.md (committed
before this ran). Funding history is cached to data/funding/<sym>.parquet
so re-runs are offline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.features.panel import (
    align_day_to_cache_precision,
    forward_return,
    trailing_percentile_rank,
)
from trading_bot.stats.bootstrap import two_group_diff_ci

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
FUNDING_DIR = Path("data/funding")
PCT_WINDOW = 90  # trailing days for the percentile rank (FIXED)
LOW_PCT, HIGH_PCT = 0.10, 0.90  # bucket thresholds (FIXED)
HORIZONS = [1, 7, 30]  # 7d is the pre-registered primary
BLOCK_DAYS = 30
N_BOOT = 5_000
SEED = 8


def fetch_funding(symbol: str) -> pl.DataFrame:
    """Full-depth funding history via ccxt, cached to parquet."""
    cache = FUNDING_DIR / f"{symbol}.parquet"
    if cache.exists():
        return pl.read_parquet(cache)
    import ccxt

    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    market = f"{symbol[:-4]}/USDT:USDT"
    since = int(datetime(2019, 9, 1, tzinfo=UTC).timestamp() * 1000)
    rows: list[tuple[int, float]] = []
    for _ in range(40):  # pages of 1000; funding since 2019 fits comfortably
        batch = exchange.fetch_funding_rate_history(market, since=since, limit=1000)
        if not batch:
            break
        rows.extend((int(r["timestamp"]), float(r["fundingRate"])) for r in batch)
        new_since = int(batch[-1]["timestamp"]) + 1
        if new_since <= since:
            break
        since = new_since
        if len(batch) < 1000:
            break
    df = pl.DataFrame(
        {"timestamp": [r[0] for r in rows], "rate": [r[1] for r in rows]}
    ).with_columns(pl.from_epoch("timestamp", time_unit="ms").dt.replace_time_zone("UTC"))
    FUNDING_DIR.mkdir(parents=True, exist_ok=True)
    df.write_parquet(cache)
    return df


def daily_panel(store: ParquetStore) -> pl.DataFrame:
    """symbol/date/funding-percentile/forward returns, all symbols stacked."""
    parts = []
    for symbol in SYMBOLS:
        funding = (
            fetch_funding(symbol)
            .with_columns(pl.col("timestamp").dt.truncate("1d").alias("day"))
            .group_by("day", maintain_order=True)
            .agg(pl.col("rate").sum().alias("funding"))
        )
        # The lake stores day at ms; the funding cache was written at us.
        # Both sides are aligned to the cache's precision or the join is empty.
        spot = align_day_to_cache_precision(
            store.read(symbol, Interval.D1).select(pl.col("timestamp").alias("day"), "close")
        )
        df = align_day_to_cache_precision(funding).join(spot, on="day", how="inner").sort("day")

        # Trailing percentile rank of today's funding within the past 90d.
        # Funding has no nulls, so this copy never filtered them.
        ranks = trailing_percentile_rank(
            df["funding"].to_list(), window=PCT_WINDOW, skip_nulls=False
        )
        df = df.with_columns(pl.Series("pct", ranks, dtype=pl.Float64))

        for h in HORIZONS:
            feature = forward_return(h)
            df = df.with_columns(**{feature.name: feature.expr})
        parts.append(df.with_columns(pl.lit(symbol).alias("symbol")))
    return pl.concat(parts).drop_nulls(["pct", "fwd7"])


def pooled_diff_ci(panel: pl.DataFrame, horizon: int) -> tuple[float, float, float]:
    """LOW-minus-HIGH mean forward return, 95% moving-block bootstrap CI.

    Blocks are contiguous DATE ranges with the cross-section kept intact
    (symbols are correlated; resampling symbol-days independently would
    fake precision).
    """
    col = f"fwd{horizon}"
    by_day = (
        panel.with_columns(
            low=(pl.col("pct") <= LOW_PCT),
            high=(pl.col("pct") >= HIGH_PCT),
        )
        .group_by("day")
        .agg(
            low_sum=pl.col(col).filter(pl.col("low")).sum(),
            low_n=pl.col("low").sum(),
            high_sum=pl.col(col).filter(pl.col("high")).sum(),
            high_n=pl.col("high").sum(),
        )
        .sort("day")
        .fill_null(0.0)
    )
    # empty_denominator="divide": this script divides the point estimate
    # directly where every other Shape-A caller guards with max(den, 1.0).
    # Identical on this data (both buckets are always populated); preserved
    # rather than normalised.
    ci = two_group_diff_ci(
        by_day["low_sum"].to_list(),
        by_day["low_n"].to_list(),
        by_day["high_sum"].to_list(),
        by_day["high_n"].to_list(),
        block=BLOCK_DAYS,
        seed=SEED,
        n_boot=N_BOOT,
        empty_denominator="divide",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    panel = daily_panel(store)
    n_days = panel["day"].n_unique()
    print(
        f"panel: {panel.height} symbol-days over {n_days} dates, "
        f"{panel['day'].min():%Y-%m-%d} .. {panel['day'].max():%Y-%m-%d}"
    )
    low = panel.filter(pl.col("pct") <= LOW_PCT)
    high = panel.filter(pl.col("pct") >= HIGH_PCT)
    mid = panel.filter((pl.col("pct") > LOW_PCT) & (pl.col("pct") < HIGH_PCT))
    print(f"bucket sizes: LOW {low.height}, MID {mid.height}, HIGH {high.height}\n")

    print(
        f"{'horizon':>8} {'E[fwd|LOW]':>11} {'E[fwd|MID]':>11} {'E[fwd|HIGH]':>12} "
        f"{'LOW-HIGH':>9} {'95% CI':>20}"
    )
    primary_pass = False
    for h in HORIZONS:
        col = f"fwd{h}"
        point, lo, hi = pooled_diff_ci(panel.drop_nulls(col), h)
        marker = " <- PRIMARY" if h == 7 else ""
        if h == 7:
            primary_pass = lo > 0.0
        print(
            f"{h:>7}d {low[col].mean():>10.2%} {mid[col].mean():>10.2%} "
            f"{high[col].mean():>11.2%} {point:>8.2%} "
            f"{'[' + f'{lo:+.2%}, {hi:+.2%}' + ']':>20}{marker}"
        )

    print("\nper-symbol LOW-minus-HIGH at 7d (pre-registered: >=5/8 positive):")
    positive = 0
    for symbol in SYMBOLS:
        sub = panel.filter(pl.col("symbol") == symbol)
        d = (sub.filter(pl.col("pct") <= LOW_PCT)["fwd7"].mean() or 0.0) - (
            sub.filter(pl.col("pct") >= HIGH_PCT)["fwd7"].mean() or 0.0
        )
        positive += d > 0
        print(f"  {symbol:<9} {d:+.2%}")

    both = primary_pass and positive >= 5
    print(
        f"\nVERDICT: CI>0 {'yes' if primary_pass else 'NO'}; "
        f"sign consistency {positive}/8 (need >=5) -> "
        f"{'H08 PASSES the kill test' if both else 'H08 FAILS'}"
    )


if __name__ == "__main__":
    main()
