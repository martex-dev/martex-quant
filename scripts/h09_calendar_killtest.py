"""Hypothesis 09 kill test: calendar effects (pre-registered sub-claims only).

    .venv/Scripts/python scripts/h09_calendar_killtest.py
"""

from __future__ import annotations

import random
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
BLOCK_DAYS = 30
N_BOOT = 5_000


def bootstrap_diff(by_day: pl.DataFrame) -> tuple[float, float, float]:
    """by_day: (day, in_sum, in_n, out_sum, out_n) -> point diff + 95% CI."""
    cols = [by_day[c].to_list() for c in ("in_sum", "in_n", "out_sum", "out_n")]
    n = by_day.height

    def prefix(xs: list[float]) -> list[float]:
        out = [0.0]
        for x in xs:
            out.append(out[-1] + float(x))
        return out

    p_is, p_in, p_os, p_on = (prefix(c) for c in cols)
    point = p_is[n] / max(p_in[n], 1.0) - p_os[n] / max(p_on[n], 1.0)
    rng = random.Random(9)
    n_blocks = n // BLOCK_DAYS + 1
    diffs = []
    for _ in range(N_BOOT):
        a = b = c = d = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, n - BLOCK_DAYS)
            e = s + BLOCK_DAYS
            a += p_is[e] - p_is[s]
            b += p_in[e] - p_in[s]
            c += p_os[e] - p_os[s]
            d += p_on[e] - p_on[s]
        if b > 0 and d > 0:
            diffs.append(a / b - c / d)
    diffs.sort()
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def day_split(panel: pl.DataFrame, flag: pl.Expr) -> pl.DataFrame:
    return (
        panel.with_columns(flag.alias("hit"))
        .group_by("day")
        .agg(
            in_sum=pl.col("ret").filter(pl.col("hit")).sum(),
            in_n=pl.col("hit").sum(),
            out_sum=pl.col("ret").filter(~pl.col("hit")).sum(),
            out_n=(~pl.col("hit")).sum(),
        )
        .sort("day")
        .fill_null(0.0)
    )


def main() -> None:
    store = ParquetStore(Path("data/lake"))

    daily_parts = []
    hourly_parts = []
    for symbol in SYMBOLS:
        d = store.read(symbol, Interval.D1).sort("timestamp")
        d = d.select(
            pl.col("timestamp").alias("day"),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("ret"),
        ).drop_nulls()
        daily_parts.append(d)
        h = store.read(symbol, Interval.H1).sort("timestamp")
        h = h.select(
            pl.col("timestamp"),
            pl.col("timestamp").dt.truncate("1d").alias("day"),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("ret"),
        ).drop_nulls()
        hourly_parts.append(h)
    daily = pl.concat(daily_parts)
    hourly = pl.concat(hourly_parts)

    results = []

    # 09a turn-of-month: last 2 + first 2 calendar days (directional: > 0)
    dom = pl.col("day").dt.day()
    month_len = pl.col("day").dt.month_end().dt.day()
    tom = (dom <= 2) | (dom >= month_len - 1)
    point, lo, hi = bootstrap_diff(day_split(daily.with_columns(pl.col("day")), tom))
    results.append(("09a turn-of-month (daily, one-sided >0)", point, lo, hi, lo > 0))

    # 09b weekend vs weekdays (two-sided)
    weekend = pl.col("day").dt.weekday() >= 6  # polars: Mon=1..Sun=7
    point, lo, hi = bootstrap_diff(day_split(daily, weekend))
    results.append(("09b weekend minus weekday (two-sided)", point, lo, hi, lo > 0 or hi < 0))

    # 09c funding-settlement hours 00/08/16 UTC (hourly, two-sided)
    fh = pl.col("timestamp").dt.hour().is_in([0, 8, 16])
    point, lo, hi = bootstrap_diff(day_split(hourly, fh))
    results.append(("09c funding hours minus others (two-sided)", point, lo, hi, lo > 0 or hi < 0))

    print(f"daily panel: {daily.height} rows; hourly panel: {hourly.height} rows\n")
    for name, point, lo, hi, ok in results:
        print(f"{name:<44} diff {point:+.4%}  CI [{lo:+.4%}, {hi:+.4%}]  "
              f"{'PASS' if ok else 'fail'}")
    n_pass = sum(r[4] for r in results)
    print(f"\nVERDICT: {n_pass}/3 sub-claims pass their pre-registered bars")


if __name__ == "__main__":
    main()
