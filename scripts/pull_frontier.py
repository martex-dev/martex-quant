"""Fetch H53/H54 data: Binance USDM taker-buy 15m klines + Bybit OI history.

    .venv/Scripts/python scripts/pull_frontier.py

Caches to data/intraday/<sym>_tb15m.parquet (ts, close, volume, taker_buy)
and data/intraday/<sym>_oi1h.parquet (ts, oi).
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
]
OUT = Path("data/intraday")
SINCE = int(datetime(2021, 1, 1, tzinfo=UTC).timestamp() * 1000)
BAR15 = 15 * 60 * 1000


def fetch_taker_buy(symbol: str) -> pl.DataFrame:
    import ccxt

    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    rows: list[tuple[int, float, float, float]] = []
    since = SINCE
    now_ms = exchange.milliseconds()
    while since < now_ms - BAR15:
        batch = None
        for attempt in range(8):
            try:
                batch = exchange.fapiPublicGetKlines(
                    {"symbol": symbol, "interval": "15m", "startTime": since, "limit": 1500}
                )
                break
            except (ccxt.RateLimitExceeded, ccxt.NetworkError):
                time.sleep(2.0**attempt)
        if batch is None:
            raise RuntimeError(f"{symbol}: persistently rate-limited")
        if not batch:
            break
        rows.extend((int(k[0]), float(k[4]), float(k[5]), float(k[9])) for k in batch)
        new_since = int(batch[-1][0]) + BAR15
        if new_since <= since:
            break
        since = new_since
        time.sleep(0.15)
    return (
        pl.DataFrame(
            {
                "ts": [r[0] for r in rows],
                "close": [r[1] for r in rows],
                "volume": [r[2] for r in rows],
                "taker_buy": [r[3] for r in rows],
            }
        )
        .with_columns(pl.from_epoch("ts", time_unit="ms").dt.replace_time_zone("UTC"))
        .unique(subset="ts")
        .sort("ts")
    )


def fetch_oi(symbol: str) -> pl.DataFrame:
    import ccxt

    exchange = ccxt.bybit({"enableRateLimit": True})
    market = f"{symbol[:-4]}/USDT:USDT"
    rows: list[tuple[int, float]] = []
    since = SINCE
    now_ms = exchange.milliseconds()
    while since < now_ms:
        batch = None
        for attempt in range(8):
            try:
                batch = exchange.fetch_open_interest_history(
                    market, timeframe="1h", since=since, limit=200
                )
                break
            except (ccxt.RateLimitExceeded, ccxt.NetworkError):
                time.sleep(2.0**attempt)
            except ccxt.BadRequest:
                batch = []
                break
        if batch is None:
            raise RuntimeError(f"{symbol}: persistently rate-limited")
        if not batch:
            since += 200 * 3_600_000
            if since >= now_ms:
                break
            continue
        rows.extend(
            (int(b["timestamp"]), float(b["openInterestAmount"] or b["openInterestValue"] or 0.0))
            for b in batch
        )
        new_since = int(batch[-1]["timestamp"]) + 3_600_000
        if new_since <= since:
            break
        since = new_since
        time.sleep(0.15)
    return (
        pl.DataFrame({"ts": [r[0] for r in rows], "oi": [r[1] for r in rows]})
        .with_columns(pl.from_epoch("ts", time_unit="ms").dt.replace_time_zone("UTC"))
        .unique(subset="ts")
        .sort("ts")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for symbol in SYMBOLS:
        path = OUT / f"{symbol}_tb15m.parquet"
        if not path.exists():
            df = fetch_taker_buy(symbol)
            df.write_parquet(path)
            print(f"{symbol} taker-buy: {df.height} bars")
    for symbol in SYMBOLS:
        path = OUT / f"{symbol}_oi1h.parquet"
        if not path.exists():
            df = fetch_oi(symbol)
            df.write_parquet(path)
            print(f"{symbol} OI: {df.height} points")


if __name__ == "__main__":
    main()
