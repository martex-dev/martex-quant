"""Pull Bybit USDT-perp 15m OHLCV for the retail intraday batch (H44-50).

    .venv/Scripts/python scripts/pull_intraday.py

Caches to data/intraday/<symbol>_15m.parquet (atomic overwrite). ~12
liquid majors, max available history. Paginates by timestamp until
`now` (short batches are NOT an end signal on Bybit) and backs off on
rate limits.
"""

from __future__ import annotations

import time
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
BAR_MS = 15 * 60 * 1000
PAUSE_S = 0.25
MIN_COMPLETE_BARS = 30_000  # smaller cache files are treated as partial


def fetch(symbol: str) -> pl.DataFrame:
    import ccxt

    exchange = ccxt.bybit({"enableRateLimit": True})
    market = f"{symbol[:-4]}/USDT:USDT"
    rows: list[list[float]] = []
    since = SINCE
    now_ms = exchange.milliseconds()
    while since < now_ms - BAR_MS:
        batch = None
        for attempt in range(8):
            try:
                batch = exchange.fetch_ohlcv(market, "15m", since=since, limit=1000)
                break
            except ccxt.RateLimitExceeded:
                time.sleep(2.0**attempt)
        if batch is None:
            raise RuntimeError(f"{symbol}: persistently rate-limited")
        if not batch:
            break
        rows.extend(batch)
        new_since = int(batch[-1][0]) + BAR_MS
        if new_since <= since:
            break
        since = new_since
        time.sleep(PAUSE_S)
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
            cached = pl.read_parquet(path)
            first_ts = cached["ts"][0]
            # Young listings legitimately have shorter history; only refetch
            # when the cache is BOTH short and claims to start at SINCE.
            if cached.height >= MIN_COMPLETE_BARS or int(first_ts.timestamp() * 1000) > SINCE:
                print(f"{symbol}: cached ({cached.height} bars)")
                continue
            print(f"{symbol}: partial cache ({cached.height} bars) — refetching")
        df = fetch(symbol)
        tmp = path.with_suffix(".tmp")
        df.write_parquet(tmp)
        tmp.replace(path)
        print(f"{symbol}: {df.height} bars, {df['ts'][0]} .. {df['ts'][-1]}")


if __name__ == "__main__":
    main()
