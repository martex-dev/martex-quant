"""Collect daily OHLCV for the BROAD Binance USDT pool, not just today's top 40.

    .venv/Scripts/python scripts/pull_pool.py

`config/universe.json` selects its 40 symbols by "top40 by 24h quote
volume, **2026-07-12**" -- a snapshot taken at the END of the research
sample. Only 8 of those 40 existed for the whole 2018-2026 backtest, and
13 listed in 2024 or later. Every rotation-family result therefore ranks
inside a pool chosen with hindsight.

H71 needs the pool a point-in-time selector would actually have had, so
this pulls every ACTIVE Binance USDT spot pair, excluding stablecoins and
leveraged tokens exactly as the universe rule does.

WHAT THIS STILL CANNOT FIX
--------------------------
Binance's API lists only pairs that are active TODAY. A coin that was a
top-40 name in 2019 and has since been delisted cannot appear here at
all. So a point-in-time universe built from this pool is *less* biased
than the hindsight universe and is still biased toward survivors, and any
result computed on it remains an UPPER bound. That limitation is stated
in docs/hypotheses/71-point-in-time-universe.md Section 7 and is not
fixable without paid point-in-time data.

This is a DATA COLLECTION step. It runs no study and decides nothing.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import ccxt
import polars as pl

OUT = Path("data/pool")
START = dt.datetime(2017, 1, 1, tzinfo=dt.UTC)
MAX_CALLS = 40

# Excluded by the same rule config/universe.json applies, so the pool this
# script builds is comparable to the universe it is meant to replace.
STABLES = frozenset(
    {
        "USDC",
        "FDUSD",
        "TUSD",
        "BUSD",
        "DAI",
        "USDP",
        "EUR",
        "TRY",
        "BRL",
        "ARS",
        "GBP",
        "AEUR",
        "XUSD",
        "USD1",
        "EURI",
        "PLN",
        "RON",
        "CZK",
        "JPY",
        "MXN",
        "COP",
        "ZAR",
        "USDS",
        "USDSB",
        "SUSD",
        "USTC",
        "UST",
        "FRAX",
        "LUSD",
        "PYUSD",
        "RLUSD",
        "USDE",
        "USDF",
        "BFUSD",
    }
)
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR", "3L", "3S", "5L", "5S")


def is_leveraged(base: str) -> bool:
    return base.endswith(LEVERAGED_SUFFIXES)


def candidate_symbols(exchange: ccxt.Exchange) -> list[tuple[str, str]]:
    """(market symbol, lake-style name) for every active, clean USDT spot pair."""
    markets = exchange.load_markets()
    out: list[tuple[str, str]] = []
    for symbol, meta in markets.items():
        if meta.get("quote") != "USDT" or not meta.get("spot") or not meta.get("active"):
            continue
        base = str(meta.get("base"))
        if base in STABLES or is_leveraged(base):
            continue
        out.append((symbol, f"{base}USDT"))
    return sorted(out, key=lambda pair: pair[1])


def fetch(exchange: ccxt.Exchange, market: str) -> pl.DataFrame | None:
    since = int(START.timestamp() * 1000)
    rows: list[list[float]] = []
    for _ in range(MAX_CALLS):
        try:
            batch = exchange.fetch_ohlcv(market, "1d", since=since, limit=1000)
        except Exception:
            return None
        if not batch:
            break
        rows.extend(batch)
        nxt = int(batch[-1][0]) + 1
        if nxt <= since:
            break
        since = nxt
        time.sleep(exchange.rateLimit / 1000.0)
        if len(batch) < 1000:
            break
    if not rows:
        return None
    unique = sorted({int(r[0]): r for r in rows}.values(), key=lambda r: int(r[0]))
    return (
        pl.DataFrame(
            {
                "timestamp": [int(r[0]) for r in unique],
                "open": [float(r[1]) for r in unique],
                "high": [float(r[2]) for r in unique],
                "low": [float(r[3]) for r in unique],
                "close": [float(r[4]) for r in unique],
                "volume": [float(r[5]) for r in unique],
            }
        )
        .with_columns(
            pl.from_epoch("timestamp", time_unit="ms")
            .dt.replace_time_zone("UTC")
            .cast(pl.Datetime("us", "UTC")),
            # Quote turnover is what the universe rule ranks on. Binance's
            # OHLCV carries base volume, so this is close*base -- the same
            # approximation scripts/pull_venues.py uses.
            (pl.col("close") * pl.col("volume")).alias("quote_volume"),
        )
        .select("timestamp", "open", "high", "low", "close", "volume", "quote_volume")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    exchange = ccxt.binance({"enableRateLimit": True})
    pairs = candidate_symbols(exchange)
    print(f"{len(pairs)} active USDT spot pairs after excluding stables and leveraged tokens\n")

    written = skipped = failed = 0
    for i, (market, name) in enumerate(pairs, 1):
        path = OUT / f"{name}.parquet"
        if path.exists():
            skipped += 1
            continue
        frame = fetch(exchange, market)
        if frame is None or frame.height == 0:
            failed += 1
            print(f"  [{i:>3}/{len(pairs)}] {name:<14} UNAVAILABLE")
            continue
        frame.write_parquet(path)
        written += 1
        if written % 25 == 0:
            print(
                f"  [{i:>3}/{len(pairs)}] {name:<14} n={frame.height:>5} "
                f"from {str(frame['timestamp'].min())[:10]}"
            )

    print(f"\nwritten {written}, already present {skipped}, unavailable {failed}")
    on_disk = sorted(OUT.glob("*.parquet"))
    print(f"pool: {len(on_disk)} symbols in {OUT}")


if __name__ == "__main__":
    main()
