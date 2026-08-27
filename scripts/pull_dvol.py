"""Collect Deribit DVOL (30-day implied volatility index) history.

    .venv/Scripts/python scripts/pull_dvol.py

DVOL is Deribit's model-free 30-day forward-looking implied volatility
index, the crypto analogue of VIX, published free and without auth at
`/public/get_volatility_index_data`. Values are annualized volatility in
PERCENT (60.0 == 60%/yr).

Only BTC and ETH have usable history (from 2021-03-24). SOL has a
408-point stub in 2022 and nothing since; XRP/MATIC have none. That
structural limit is a property of the venue, not of this collector, and
is recorded in docs/hypotheses/67-variance-risk-premium.md Section 7.

This is a DATA COLLECTION step. It runs no study and decides nothing.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

import polars as pl

API = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
OUT = Path("data/dvol")
CURRENCIES = ("BTC", "ETH")
RESOLUTION = "1D"
START = dt.datetime(2021, 1, 1, tzinfo=dt.UTC)


def _fetch(currency: str, start_ms: int, end_ms: int) -> list[list[float]]:
    url = (
        f"{API}?currency={currency}"
        f"&start_timestamp={start_ms}&end_timestamp={end_ms}"
        f"&resolution={RESOLUTION}"
    )
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    return list(payload["result"]["data"])


def pull(currency: str) -> pl.DataFrame:
    """Year-by-year pull; the endpoint truncates long ranges silently."""
    rows: list[list[float]] = []
    year = START.year
    now = dt.datetime.now(tz=dt.UTC)
    while year <= now.year:
        start = dt.datetime(year, 1, 1, tzinfo=dt.UTC)
        end = dt.datetime(year + 1, 1, 1, tzinfo=dt.UTC)
        chunk = _fetch(
            currency, int(start.timestamp() * 1000), int(end.timestamp() * 1000)
        )
        print(f"  {currency} {year}: {len(chunk)} bars")
        rows.extend(chunk)
        year += 1
        time.sleep(0.3)

    frame = (
        pl.DataFrame(
            rows,
            schema=["ts_ms", "open", "high", "low", "close"],
            orient="row",
        )
        .with_columns(
            pl.from_epoch(pl.col("ts_ms").cast(pl.Int64), time_unit="ms")
            .dt.replace_time_zone("UTC")
            .alias("timestamp")
        )
        .select("timestamp", "open", "high", "low", "close")
        .unique(subset="timestamp", keep="last")
        .sort("timestamp")
    )
    return frame


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for currency in CURRENCIES:
        print(f"{currency}:")
        frame = pull(currency)
        path = OUT / f"{currency}.parquet"
        frame.write_parquet(path)
        print(
            f"  -> {path}  n={frame.height}  "
            f"{str(frame['timestamp'].min())[:10]} -> "
            f"{str(frame['timestamp'].max())[:10]}  "
            f"close min/mean/max = {frame['close'].min():.1f}/"
            f"{frame['close'].mean():.1f}/{frame['close'].max():.1f}"
        )


if __name__ == "__main__":
    main()
