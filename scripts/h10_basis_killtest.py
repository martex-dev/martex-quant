"""Hypothesis 10 kill test: spot-vs-perp basis extremes vs forward returns.

    .venv/Scripts/python scripts/h10_basis_killtest.py

Perp daily closes fetched once and cached to data/perp/<sym>.parquet.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
PERP_DIR = Path("data/perp")
PCT_WINDOW = 90
LOW_PCT, HIGH_PCT = 0.10, 0.90
HORIZONS = [1, 7, 30]
BLOCK_DAYS = 30
N_BOOT = 5_000


def fetch_perp_daily(symbol: str) -> pl.DataFrame:
    cache = PERP_DIR / f"{symbol}.parquet"
    if cache.exists():
        return pl.read_parquet(cache)
    import ccxt

    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    market = f"{symbol[:-4]}/USDT:USDT"
    since = int(datetime(2019, 9, 1, tzinfo=UTC).timestamp() * 1000)
    rows: list[tuple[int, float]] = []
    for _ in range(10):
        batch = exchange.fetch_ohlcv(market, "1d", since=since, limit=1000)
        if not batch:
            break
        rows.extend((int(b[0]), float(b[4])) for b in batch)
        new_since = int(batch[-1][0]) + 1
        if new_since <= since:
            break
        since = new_since
        if len(batch) < 1000:
            break
    df = pl.DataFrame(
        {"day": [r[0] for r in rows], "perp_close": [r[1] for r in rows]}
    ).with_columns(pl.from_epoch("day", time_unit="ms").dt.replace_time_zone("UTC"))
    PERP_DIR.mkdir(parents=True, exist_ok=True)
    df.write_parquet(cache)
    return df


def build_panel(store: ParquetStore) -> pl.DataFrame:
    parts = []
    for symbol in SYMBOLS:
        perp = fetch_perp_daily(symbol).with_columns(pl.col("day").cast(pl.Datetime("us", "UTC")))
        spot = (
            store.read(symbol, Interval.D1)
            .select(pl.col("timestamp").alias("day"), "close")
            .with_columns(pl.col("day").cast(pl.Datetime("us", "UTC")))
        )
        df = (
            perp.join(spot, on="day", how="inner")
            .sort("day")
            .with_columns(basis=pl.col("perp_close") / pl.col("close") - 1.0)
        )
        values = df["basis"].to_list()
        pct: list[float | None] = []
        for i, v in enumerate(values):
            if i < PCT_WINDOW:
                pct.append(None)
                continue
            window = values[i - PCT_WINDOW : i + 1]
            pct.append(sum(1 for w in window if w <= v) / len(window))
        df = df.with_columns(pl.Series("pct", pct, dtype=pl.Float64))
        for h in HORIZONS:
            df = df.with_columns(
                (pl.col("close").shift(-h) / pl.col("close") - 1.0).alias(f"fwd{h}")
            )
        parts.append(df.with_columns(pl.lit(symbol).alias("symbol")))
    return pl.concat(parts).drop_nulls(["pct", "fwd7"])


def pooled_diff_ci(panel: pl.DataFrame, horizon: int) -> tuple[float, float, float]:
    col = f"fwd{horizon}"
    by_day = (
        panel.with_columns(low=(pl.col("pct") <= LOW_PCT), high=(pl.col("pct") >= HIGH_PCT))
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
    arrays = [by_day[c].to_list() for c in ("low_sum", "low_n", "high_sum", "high_n")]
    n = by_day.height

    def prefix(xs: list[float]) -> list[float]:
        out = [0.0]
        for x in xs:
            out.append(out[-1] + float(x))
        return out

    p_ls, p_ln, p_hs, p_hn = (prefix(a) for a in arrays)
    point = p_ls[n] / max(p_ln[n], 1.0) - p_hs[n] / max(p_hn[n], 1.0)
    rng = random.Random(10)
    n_blocks = n // BLOCK_DAYS + 1
    diffs = []
    for _ in range(N_BOOT):
        ls = ln = hs = hn = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, n - BLOCK_DAYS)
            e = s + BLOCK_DAYS
            ls += p_ls[e] - p_ls[s]
            ln += p_ln[e] - p_ln[s]
            hs += p_hs[e] - p_hs[s]
            hn += p_hn[e] - p_hn[s]
        if ln > 0 and hn > 0:
            diffs.append(ls / ln - hs / hn)
    diffs.sort()
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    panel = build_panel(store)
    print(
        f"panel: {panel.height} symbol-days, {panel['day'].min():%Y-%m-%d} .. "
        f"{panel['day'].max():%Y-%m-%d}; "
        f"median |basis| {panel['basis'].abs().median():.4%}\n"
    )
    low = panel.filter(pl.col("pct") <= LOW_PCT)
    high = panel.filter(pl.col("pct") >= HIGH_PCT)
    print(f"{'horizon':>8} {'E[fwd|LOW]':>11} {'E[fwd|HIGH]':>12} {'LOW-HIGH':>9} {'95% CI':>20}")
    primary_pass = False
    for h in HORIZONS:
        col = f"fwd{h}"
        point, lo, hi = pooled_diff_ci(panel.drop_nulls(col), h)
        if h == 7:
            primary_pass = lo > 0.0
        print(
            f"{h:>7}d {low[col].mean():>10.2%} {high[col].mean():>11.2%} {point:>8.2%} "
            f"{'[' + f'{lo:+.2%}, {hi:+.2%}' + ']':>20}{' <- PRIMARY' if h == 7 else ''}"
        )

    positive = 0
    print("\nper-symbol LOW-minus-HIGH at 7d (need >=5/8 positive):")
    for symbol in SYMBOLS:
        sub = panel.filter(pl.col("symbol") == symbol)
        d = (sub.filter(pl.col("pct") <= LOW_PCT)["fwd7"].mean() or 0.0) - (
            sub.filter(pl.col("pct") >= HIGH_PCT)["fwd7"].mean() or 0.0
        )
        positive += d > 0
        print(f"  {symbol:<9} {d:+.2%}")

    verdict = primary_pass and positive >= 5
    print(
        f"\nVERDICT: CI>0 {'yes' if primary_pass else 'NO'}; consistency {positive}/8 -> "
        f"{'H10 PASSES' if verdict else 'H10 FAILS'}"
    )


if __name__ == "__main__":
    main()
