"""Collect the BROAD Binance USDM perp pool: daily OHLCV plus funding history.

    .venv/Scripts/python scripts/pull_perp_pool.py

H71 showed the deployed momentum spec keeps only 58% of its Sharpe once
its universe is chosen point-in-time rather than at the end of the
sample. Carry is the project's other validated edge and it ranks inside
the same hindsight universe, so it needs the same test -- and a carry
book trades PERPS, so its universe must be selected on perp liquidity.

This pulls every active USDT-margined Binance perp (698 at collection):
daily OHLCV with quote turnover for the selector, and full 8-hour funding
history for the payoff.

STRICTLY SEPARATE FROM THE EXISTING CACHES
------------------------------------------
Writes to data/perp_pool/ and data/funding_pool/, never to data/perp/ or
data/funding/. The frozen goldens for h62/h63/h64/h65/h66 fingerprint the
existing caches byte-for-byte; touching them would invalidate five
published verdicts to gain nothing.

WHAT THIS STILL CANNOT FIX
--------------------------
Binance lists only perps active TODAY. A contract that traded in 2021 and
has since been delisted cannot appear here. For carry that limitation may
bite HARDER than it did for momentum: perps are typically delisted after
a collapse, and a short-perp position through a collapse-and-squeeze is
exactly where carry's tail risk lives. So the missing streams are
plausibly the bad ones, and any result computed on this pool is an UPPER
bound. Stated in docs/hypotheses/72-point-in-time-carry.md Section 7.

This is a DATA COLLECTION step. It runs no study and decides nothing.
"""

from __future__ import annotations

import time
from pathlib import Path

import ccxt
import polars as pl

PERP_OUT = Path("data/perp_pool")
FUNDING_OUT = Path("data/funding_pool")
SINCE_MS = 1_500_000_000_000  # 2017-07-14; before any USDM perp listing
PAGE_LIMIT = 1000
MAX_PAGES = 60


def perp_markets(exchange: ccxt.Exchange) -> list[tuple[str, str]]:
    """(market symbol, lake-style name) for every active USDT-margined perp."""
    markets = exchange.load_markets()
    out: list[tuple[str, str]] = []
    for symbol, meta in markets.items():
        if not (meta.get("swap") and meta.get("linear") and meta.get("active")):
            continue
        if meta.get("settle") != "USDT":
            continue
        out.append((symbol, f"{meta.get('base')}USDT"))
    return sorted(out, key=lambda pair: pair[1])


def fetch_funding(exchange: ccxt.Exchange, market: str) -> pl.DataFrame | None:
    rows: list[tuple[int, float]] = []
    since = SINCE_MS
    for _ in range(MAX_PAGES):
        try:
            batch = exchange.fetch_funding_rate_history(market, since=since, limit=PAGE_LIMIT)
        except (ccxt.RateLimitExceeded, ccxt.NetworkError):
            time.sleep(2.0)
            continue
        except Exception:
            return None
        if not batch:
            break
        rows.extend((int(r["timestamp"]), float(r["fundingRate"])) for r in batch)
        nxt = int(batch[-1]["timestamp"]) + 1
        if nxt <= since:
            break
        since = nxt
        if len(batch) < PAGE_LIMIT:
            break
    if not rows:
        return None
    return (
        pl.DataFrame({"timestamp": [r[0] for r in rows], "rate": [r[1] for r in rows]})
        .unique(subset="timestamp")
        .sort("timestamp")
        .with_columns(pl.from_epoch("timestamp", time_unit="ms").dt.replace_time_zone("UTC"))
    )


def fetch_perp_daily(exchange: ccxt.Exchange, market: str) -> pl.DataFrame | None:
    """Daily perp closes plus quote turnover -- the selector ranks on turnover."""
    rows: list[tuple[int, float, float]] = []
    since = SINCE_MS
    for _ in range(MAX_PAGES):
        try:
            batch = exchange.fetch_ohlcv(market, "1d", since=since, limit=PAGE_LIMIT)
        except (ccxt.RateLimitExceeded, ccxt.NetworkError):
            time.sleep(2.0)
            continue
        except Exception:
            return None
        if not batch:
            break
        rows.extend((int(b[0]), float(b[4]), float(b[5])) for b in batch)
        nxt = int(batch[-1][0]) + 1
        if nxt <= since:
            break
        since = nxt
        if len(batch) < PAGE_LIMIT:
            break
    if not rows:
        return None
    return (
        pl.DataFrame(
            {
                "day": [r[0] for r in rows],
                "perp_close": [r[1] for r in rows],
                "base_volume": [r[2] for r in rows],
            }
        )
        .unique(subset="day")
        .sort("day")
        .with_columns(
            pl.from_epoch("day", time_unit="ms").dt.replace_time_zone("UTC"),
            (pl.col("perp_close") * pl.col("base_volume")).alias("quote_volume"),
        )
        .select("day", "perp_close", "quote_volume")
    )


def main() -> None:
    PERP_OUT.mkdir(parents=True, exist_ok=True)
    FUNDING_OUT.mkdir(parents=True, exist_ok=True)
    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    pairs = perp_markets(exchange)
    print(f"{len(pairs)} active USDT-margined perps\n")

    done = skipped = failed = 0
    for i, (market, name) in enumerate(pairs, 1):
        p_path = PERP_OUT / f"{name}.parquet"
        f_path = FUNDING_OUT / f"{name}.parquet"
        if p_path.exists() and f_path.exists():
            skipped += 1
            continue

        perp = fetch_perp_daily(exchange, market) if not p_path.exists() else None
        funding = fetch_funding(exchange, market) if not f_path.exists() else None
        if (not p_path.exists() and perp is None) or (not f_path.exists() and funding is None):
            failed += 1
            print(f"  [{i:>3}/{len(pairs)}] {name:<14} no history returned")
            continue
        if perp is not None:
            perp.write_parquet(p_path)
        if funding is not None:
            funding.write_parquet(f_path)
        done += 1
        if done % 40 == 0:
            print(f"  [{i:>3}/{len(pairs)}] {name:<14} written {done}")

    print(f"\nwritten {done}, already present {skipped}, unavailable {failed}")
    print(
        f"pool: {len(list(PERP_OUT.glob('*.parquet')))} perp, "
        f"{len(list(FUNDING_OUT.glob('*.parquet')))} funding"
    )


if __name__ == "__main__":
    main()
