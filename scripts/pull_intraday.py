"""Pull Bybit USDT-perp 15m OHLCV for the retail intraday batch (H44-50).

    .venv/Scripts/python scripts/pull_intraday.py

Caches to data/intraday/<symbol>_15m.parquet (append-safe: full refetch,
atomic overwrite). ~12 liquid majors, max available history.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LTCUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "TRXUSDT",
    "PEPEUSDT",
]
OUT = Path("data/intraday")
SINCE = int(datetime(2021, 1, 1, tzinfo=UTC).timestamp() * 1000)
STEP_LIMIT = 1000


def fetch(symbol: str) -> pl.DataFrame:
    import ccxt

    exchange = ccxt.bybit({"enableRateLimit": True})
    market = f"{symbol[:-4]}/USDT:USDT"
    rows: list[list[float]] = []
    since = SINCE
    while True:
        batch = exchange.fetch_ohlcv(market, "15m", since=since, limit=STEP_LIMIT)
        if not batch:
            break
        rows.extend(batch)
        new_since = int(batch[-1][0]) + 1
        if new_since <= since or len(batch) < STEP_LIMIT:
            break
        since = new_since
    df = pl.DataFrame(
        {
            "ts": [int(r[0]) for r in rows],
            "open": [float(r[1]) for r in rows],
            "high": [float(r[2]) for r in rows],
            "low": [float(r[3]) for r in rows],
            "close": [float(r[4]) for r in rows],
            "volume": [float(r[5]) for r in rows],
        }
    ).with_columns(pl.from_epoch("ts", time_unit="ms").dt.replace_time_zone("UTC"))
    return df.unique(subset="ts").sort("ts")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for symbol in SYMBOLS:
        path = OUT / f"{symbol}_15m.parquet"
        if path.exists():
            print(f"{symbol}: cached ({pl.read_parquet(path).height} bars)")
            continue
        df = fetch(symbol)
        tmp = path.with_suffix(".tmp")
        df.write_parquet(tmp)
        tmp.replace(path)
        print(f"{symbol}: {df.height} bars, {df['ts'][0]} .. {df['ts'][-1]}")


if __name__ == "__main__":
    main()
