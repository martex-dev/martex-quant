"""Extend the funding / perp caches from 8 majors to the whole universe.

    .venv/Scripts/python scripts/pull_carry_universe.py

Family F1 of docs/research/family-expansion-program.md needs funding and
perp history for more than the eight majors H62/H63 used. This fetches the
rest of config/universe.json from Binance USDM.

STRICTLY ADDITIVE, AND THAT IS NOT A STYLE CHOICE
-------------------------------------------------
An existing cache file is never re-fetched or rewritten. The frozen
goldens for h62/h63/h64 fingerprint data/funding/BTCUSDT.parquet and
data/perp/BTCUSDT.parquet byte-for-byte, so re-pulling a symbol that
already has a file would invalidate three published verdicts to gain
nothing. Symbols already present are skipped and reported as skipped.

The new files run to today while the existing eight stop at 2026-07-11 and
the spot lake ends 2026-07-10. That asymmetry is harmless: every carry
study inner-joins spot, perp and funding on date, so trailing rows with no
spot bar are dropped. It is recorded here so nobody later mistakes the
ragged end for a bug.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import polars as pl

FUNDING_DIR = Path("data/funding")
PERP_DIR = Path("data/perp")
UNIVERSE = Path("config/universe.json")
SINCE_MS = 1_500_000_000_000  # 2017-07-14; before any USDM perp listing
PAGE_LIMIT = 1000
MAX_PAGES = 60


def _client():  # noqa: ANN202
    import ccxt

    return ccxt.binanceusdm({"enableRateLimit": True})


def fetch_funding(exchange, market: str) -> pl.DataFrame | None:  # noqa: ANN001
    """Full-depth 8-hour funding history, paged forward."""
    import ccxt

    rows: list[tuple[int, float]] = []
    since = SINCE_MS
    for _ in range(MAX_PAGES):
        try:
            batch = exchange.fetch_funding_rate_history(market, since=since, limit=PAGE_LIMIT)
        except (ccxt.RateLimitExceeded, ccxt.NetworkError):
            time.sleep(2.0)
            continue
        except ccxt.BadSymbol:
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


def fetch_perp_daily(exchange, market: str) -> pl.DataFrame | None:  # noqa: ANN001
    """Daily perp closes, paged forward."""
    import ccxt

    rows: list[tuple[int, float]] = []
    since = SINCE_MS
    for _ in range(MAX_PAGES):
        try:
            batch = exchange.fetch_ohlcv(market, "1d", since=since, limit=PAGE_LIMIT)
        except (ccxt.RateLimitExceeded, ccxt.NetworkError):
            time.sleep(2.0)
            continue
        except ccxt.BadSymbol:
            return None
        if not batch:
            break
        rows.extend((int(b[0]), float(b[4])) for b in batch)
        nxt = int(batch[-1][0]) + 1
        if nxt <= since:
            break
        since = nxt
        if len(batch) < PAGE_LIMIT:
            break
    if not rows:
        return None
    return (
        pl.DataFrame({"day": [r[0] for r in rows], "perp_close": [r[1] for r in rows]})
        .unique(subset="day")
        .sort("day")
        .with_columns(pl.from_epoch("day", time_unit="ms").dt.replace_time_zone("UTC"))
    )


def main() -> None:
    FUNDING_DIR.mkdir(parents=True, exist_ok=True)
    PERP_DIR.mkdir(parents=True, exist_ok=True)
    symbols = json.loads(UNIVERSE.read_text(encoding="utf-8"))["symbols"]
    exchange = _client()
    exchange.load_markets()

    added, skipped, missing = 0, 0, []
    for symbol in symbols:
        f_path = FUNDING_DIR / f"{symbol}.parquet"
        p_path = PERP_DIR / f"{symbol}.parquet"
        if f_path.exists() and p_path.exists():
            skipped += 1
            continue

        base = symbol.removesuffix("USDT")
        market = f"{base}/USDT:USDT"
        if market not in exchange.markets:
            missing.append(symbol)
            print(f"  {symbol:<12} no USDM perp market")
            continue

        funding = fetch_funding(exchange, market) if not f_path.exists() else None
        perp = fetch_perp_daily(exchange, market) if not p_path.exists() else None
        if (not f_path.exists() and funding is None) or (not p_path.exists() and perp is None):
            missing.append(symbol)
            print(f"  {symbol:<12} no history returned")
            continue

        if funding is not None:
            funding.write_parquet(f_path)
        if perp is not None:
            perp.write_parquet(p_path)
        added += 1
        n_f = funding.height if funding is not None else "kept"
        n_p = perp.height if perp is not None else "kept"
        span = str(funding["timestamp"].min())[:10] if funding is not None else "?"
        print(f"  {symbol:<12} funding={n_f!s:<6} perp={n_p!s:<6} from {span}")

    print(f"\nadded {added}, skipped {skipped} already cached, {len(missing)} unavailable")
    if missing:
        print("unavailable:", ", ".join(missing))


if __name__ == "__main__":
    main()
