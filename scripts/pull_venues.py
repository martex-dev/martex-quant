"""Collect daily closes for the same assets across four spot venues.

    .venv/Scripts/python scripts/pull_venues.py

The cross-venue dataset family F2 needs, and the single most valuable one
this project did not have. Two USD (fiat-quoted) venues and two USDT
(offshore) venues, plus a USDT/USD peg series so the two quote currencies
can be compared in the same units at all.

Venue choices, and what they cost:

- **Binance / OKX** (USDT): both paginate to 2019 cleanly.
- **Coinbase Exchange / Bitstamp** (USD): both paginate to 2019 cleanly.
- **Bitfinex USDT/USD**: the peg. Reaches 2018-11-27, deeper than any
  other source checked (Coinbase, OKX and Bitstamp return nothing for
  this pair; Kraken is capped, see below).
- **Bybit EXCLUDED**: spot history starts 2021-07-05. Including it as a
  third USDT venue would cost ~30% of the study window.
- **Kraken EXCLUDED**: its OHLC endpoint returns only the most recent
  ~720 candles regardless of `since`, so it cannot supply history at all.

All venues stamp daily bars at 00:00 UTC, so closes are synchronous
across venues without resampling. Verified 2026-08-27: a fresh Binance
BTC/USDT pull is byte-identical to the frozen research lake on all 2,747
overlapping days.

This is a DATA COLLECTION step. It runs no study and decides nothing.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import ccxt
import polars as pl

OUT = Path("data/venues")
START = dt.datetime(2019, 1, 1, tzinfo=dt.UTC)

# Fixed by availability, not by preference: these are the universe bases
# quoted on ALL FOUR venues (checked against each venue's market list).
SYMBOLS = (
    "AAVE",
    "ADA",
    "ARB",
    "BNB",
    "BTC",
    "DOGE",
    "ENA",
    "ETH",
    "HBAR",
    "LINK",
    "LTC",
    "NEAR",
    "PEPE",
    "SKL",
    "SOL",
    "SUI",
    "TAO",
    "UNI",
    "VIRTUAL",
    "WLD",
    "XLM",
    "XPL",
    "XRP",
    "ZEC",
)
VENUES = (
    ("binance", "USDT"),
    ("okx", "USDT"),
    ("coinbaseexchange", "USD"),
    ("bitstamp", "USD"),
)
PEG = ("bitfinex", "USDT/USD")
MAX_CALLS = 80


def _first_available(exchange: ccxt.Exchange, market: str) -> int | None:
    """Earliest `since` (ms) that returns data, walking forward by year.

    Coinbase Exchange and OKX both return an EMPTY list when `since`
    predates the pair's listing, rather than clamping to the first
    available candle. Taking that emptiness at face value silently
    dropped 18 of 24 Coinbase series and 22 of 24 OKX series on the first
    run of this collector. The walk is the fix: the first year that
    answers is the listing year, and pagination proceeds from there.
    """
    for year in range(START.year, dt.datetime.now(tz=dt.UTC).year + 1):
        since = int(dt.datetime(year, 1, 1, tzinfo=dt.UTC).timestamp() * 1000)
        try:
            # limit MUST be large. These venues serve the window
            # [since, since + limit*granularity], so probing with a small
            # limit only asks "was it listed in the first N days of this
            # year?" and pushes every mid-year listing into the following
            # January. That silently cost Coinbase SOL seven months and
            # ADA/DOGE two years before it was caught.
            batch = exchange.fetch_ohlcv(market, "1d", since=since, limit=1000)
        except Exception as exc:
            print(f"      probe {market} {year}: {type(exc).__name__}: {str(exc)[:70]}")
            return None
        time.sleep(exchange.rateLimit / 1000.0)
        if batch:
            # Start from the first candle that actually exists, not from
            # the January the probe happened to succeed in.
            return int(batch[0][0])
    return None


def fetch(exchange: ccxt.Exchange, market: str) -> pl.DataFrame | None:
    """Paginate daily OHLCV from the pair's listing to now."""
    start = _first_available(exchange, market)
    if start is None:
        return None
    since = start
    now_ms = int(dt.datetime.now(tz=dt.UTC).timestamp() * 1000)
    rows: list[list[float]] = []
    empties = 0
    for _ in range(MAX_CALLS):
        try:
            batch = exchange.fetch_ohlcv(market, "1d", since=since, limit=1000)
        except Exception as exc:
            print(f"      fetch {market}: {type(exc).__name__}: {str(exc)[:70]}")
            break
        if not batch:
            # An empty batch mid-series is a TRADING GAP, not the end of
            # history. Coinbase suspended XRP/USD from 2021-01-19 to
            # 2023-07 over the SEC suit; breaking on the first empty batch
            # silently truncated that series at the delisting and cost
            # three years. Step over the hole instead, and only give up
            # after a long stretch of genuine silence.
            empties += 1
            if empties > 24 or since >= now_ms:
                break
            since += 90 * 86_400_000
            time.sleep(exchange.rateLimit / 1000.0)
            continue
        empties = 0
        rows.extend(batch)
        nxt = int(batch[-1][0]) + 1
        if nxt <= since:
            break
        since = nxt
        time.sleep(exchange.rateLimit / 1000.0)
    if not rows:
        return None
    unique = sorted({int(r[0]): r for r in rows}.values(), key=lambda r: int(r[0]))
    return (
        pl.DataFrame(
            {
                "timestamp": [int(r[0]) for r in unique],
                "close": [float(r[4]) for r in unique],
                "base_volume": [float(r[5]) for r in unique],
            }
        )
        .with_columns(
            pl.from_epoch("timestamp", time_unit="ms")
            .dt.replace_time_zone("UTC")
            .cast(pl.Datetime("us", "UTC")),
            # Quote-currency turnover. The study needs this to refuse a
            # "price" that is really a stale last trade on a dead pair.
            (pl.col("close") * pl.col("base_volume")).alias("quote_volume"),
        )
        .select("timestamp", "close", "quote_volume")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    for venue, quote in VENUES:
        exchange = getattr(ccxt, venue)({"enableRateLimit": True})
        exchange.load_markets()
        kept = 0
        for base in SYMBOLS:
            path = OUT / f"{venue}_{base}.parquet"
            if path.exists():
                kept += 1
                continue
            frame = fetch(exchange, f"{base}/{quote}")
            if frame is None or frame.height == 0:
                print(f"  {venue:18} {base:8} UNAVAILABLE")
                continue
            frame.write_parquet(path)
            kept += 1
            print(
                f"  {venue:18} {base:8} n={frame.height:>5}  "
                f"{str(frame['timestamp'].min())[:10]} -> "
                f"{str(frame['timestamp'].max())[:10]}"
            )
        print(f"{venue}: {kept}/{len(SYMBOLS)} series on disk\n")

    peg_venue, peg_market = PEG
    peg_path = OUT / "peg_usdt_usd.parquet"
    if not peg_path.exists():
        exchange = getattr(ccxt, peg_venue)({"enableRateLimit": True})
        frame = fetch(exchange, peg_market)
        if frame is None:
            raise RuntimeError(f"peg series {peg_market} unavailable on {peg_venue}")
        frame.write_parquet(peg_path)
    peg = pl.read_parquet(peg_path)
    print(
        f"peg ({peg_venue} {peg_market}): n={peg.height}  "
        f"{str(peg['timestamp'].min())[:10]} -> {str(peg['timestamp'].max())[:10]}  "
        f"close min/mean/max = {peg['close'].min():.4f}/"
        f"{peg['close'].mean():.4f}/{peg['close'].max():.4f}"
    )


if __name__ == "__main__":
    main()
