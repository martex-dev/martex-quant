"""Hypotheses 13 (shock persistence) + 14 (vol-expansion breakout) kill tests.

    .venv/Scripts/python scripts/h13_h14_killtests.py

Specs pre-registered in docs/hypotheses/13-*.md and 14-*.md.
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


def diff_ci(panel: pl.DataFrame, col_a: str, col_b: str, seed: int) -> tuple[float, float, float]:
    """Mean(col_a values) - mean(col_b values), block-bootstrapped by date.

    col_a/col_b are 'value if member else null' columns on a shared panel.
    """
    by_day = (
        panel.group_by("day")
        .agg(
            a_sum=pl.col(col_a).sum(),
            a_n=pl.col(col_a).is_not_null().sum(),
            b_sum=pl.col(col_b).sum(),
            b_n=pl.col(col_b).is_not_null().sum(),
        )
        .sort("day")
        .fill_null(0.0)
    )
    arrays = [by_day[c].to_list() for c in ("a_sum", "a_n", "b_sum", "b_n")]
    n = by_day.height

    def prefix(xs: list[float]) -> list[float]:
        out = [0.0]
        for x in xs:
            out.append(out[-1] + float(x))
        return out

    pa, pan, pb, pbn = (prefix(a) for a in arrays)
    point = pa[n] / max(pan[n], 1.0) - pb[n] / max(pbn[n], 1.0)
    rng = random.Random(seed)
    n_blocks = n // BLOCK_DAYS + 1
    diffs = []
    for _ in range(N_BOOT):
        sa = na = sb = nb = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, n - BLOCK_DAYS)
            e = s + BLOCK_DAYS
            sa += pa[e] - pa[s]
            na += pan[e] - pan[s]
            sb += pb[e] - pb[s]
            nb += pbn[e] - pbn[s]
        if na > 0 and nb > 0:
            diffs.append(sa / na - sb / nb)
    diffs.sort()
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def build_panel(store: ParquetStore) -> pl.DataFrame:
    parts = []
    for symbol in SYMBOLS:
        df = store.read(symbol, Interval.D1).sort("timestamp")
        df = df.select(
            pl.col("timestamp").alias("day"),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("ret"),
            pl.col("close"),
        )
        df = df.with_columns(
            vol30=pl.col("ret").shift(1).rolling_std(30),
            vol10=pl.col("ret").shift(1).rolling_std(10),
        )
        # Trailing-365d percentile of vol10 (for compression detection).
        vols = df["vol10"].to_list()
        pct: list[float | None] = []
        for i, v in enumerate(vols):
            if v is None or i < 365:
                pct.append(None)
                continue
            window = [w for w in vols[i - 365 : i + 1] if w is not None]
            pct.append(sum(1 for w in window if w <= v) / len(window))
        df = df.with_columns(pl.Series("vol10_pct", pct, dtype=pl.Float64))
        for h in (1, 3, 7):
            df = df.with_columns(
                (pl.col("close").shift(-h) / pl.col("close") - 1.0).alias(f"fwd{h}")
            )
        parts.append(df.with_columns(pl.lit(symbol).alias("symbol")))
    return pl.concat(parts).drop_nulls(["ret", "vol30", "fwd7"])


def h13(panel: pl.DataFrame) -> None:
    print("=== H13 shock persistence (fwd 7d minus quiet-day baseline) ===")
    panel = panel.with_columns(z=pl.col("ret") / pl.col("vol30"))
    buckets = {
        "extreme up (z>=2)": pl.col("z") >= 2,
        "moderate up (1<=z<2)": (pl.col("z") >= 1) & (pl.col("z") < 2),
        "moderate down": (pl.col("z") > -2) & (pl.col("z") <= -1),
        "extreme down (z<=-2)": pl.col("z") <= -2,
    }
    baseline = pl.col("z").abs() < 1
    passes = 0
    for i, (name, cond) in enumerate(buckets.items()):
        p = panel.with_columns(
            a=pl.when(cond).then(pl.col("fwd7")),
            b=pl.when(baseline).then(pl.col("fwd7")),
        )
        n_a = p["a"].drop_nulls().len()
        point, lo, hi = diff_ci(p, "a", "b", seed=13 + i)
        sig = lo > 0 or hi < 0
        passes += sig
        print(
            f"  {name:<22} n={n_a:>5}  diff {point:+.2%}  CI [{lo:+.2%}, {hi:+.2%}]  "
            f"{'SIGNAL' if sig else 'noise'}"
        )
    print(f"  H13: {passes}/4 buckets carry signal at 7d\n")


def h14(panel: pl.DataFrame) -> None:
    print("=== H14 vol-expansion breakout (directional fwd 7d) ===")
    panel = panel.drop_nulls(["vol10", "vol10_pct"])
    trigger = pl.col("ret").abs() > 2 * pl.col("vol10")
    compressed = pl.col("vol10_pct") <= 0.20
    direction = pl.col("ret").sign()
    panel = panel.with_columns(dir_fwd7=pl.col("fwd7") * direction)

    # Bar 1: signal days' directional fwd7 > 0 (vs zero -> compare to nothing;
    # implement as a vs b where b is the SAME column on all-days shuffled? No —
    # test mean>0 via bootstrap of the signal-day series itself).
    signal = panel.filter(trigger & compressed)
    values = signal.group_by("day").agg(s=pl.col("dir_fwd7").sum(), n=pl.len()).sort("day")
    sums, ns = values["s"].to_list(), values["n"].to_list()
    n = len(sums)
    rng = random.Random(14)
    point = sum(sums) / max(sum(ns), 1)
    boots = []
    if n > BLOCK_DAYS:
        n_blocks = n // BLOCK_DAYS + 1
        for _ in range(N_BOOT):
            ts = tn = 0.0
            for _ in range(n_blocks):
                s = rng.randint(0, n - BLOCK_DAYS)
                ts += sum(sums[s : s + BLOCK_DAYS])
                tn += sum(ns[s : s + BLOCK_DAYS])
            if tn > 0:
                boots.append(ts / tn)
        boots.sort()
        lo1, hi1 = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))]
    else:
        lo1, hi1 = float("nan"), float("nan")
    bar1 = lo1 > 0
    print(
        f"  compression+trigger days: {signal.height}  directional fwd7 {point:+.2%}  "
        f"CI [{lo1:+.2%}, {hi1:+.2%}]  {'PASS' if bar1 else 'fail'}"
    )

    # Bar 2: increment over trigger-without-compression.
    p = panel.with_columns(
        a=pl.when(trigger & compressed).then(pl.col("dir_fwd7")),
        b=pl.when(trigger & ~compressed).then(pl.col("dir_fwd7")),
    )
    point2, lo2, hi2 = diff_ci(p, "a", "b", seed=141)
    bar2 = lo2 > 0
    print(
        f"  increment vs trigger-without-compression: {point2:+.2%}  "
        f"CI [{lo2:+.2%}, {hi2:+.2%}]  {'PASS' if bar2 else 'fail'}"
    )
    print(f"  H14: {'PASSES' if bar1 and bar2 else 'FAILS'} (needs both)\n")


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    panel = build_panel(store)
    print(f"panel: {panel.height} symbol-days\n")
    h13(panel)
    h14(panel)


if __name__ == "__main__":
    main()
