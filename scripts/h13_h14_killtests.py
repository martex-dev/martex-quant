"""Hypotheses 13 (shock persistence) + 14 (vol-expansion breakout) kill tests.

    .venv/Scripts/python scripts/h13_h14_killtests.py

Specs pre-registered in docs/hypotheses/13-*.md and 14-*.md.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.features.panel import daily_panel as canonical_daily_panel
from trading_bot.features.panel import (
    forward_return,
    trailing_percentile_rank,
    vol_excl_current,
)
from trading_bot.stats.bootstrap import event_mean_ci, two_group_diff_ci
from trading_bot.stats.significance import ci_above_zero, ci_excludes_zero

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
    a_sum, a_n, b_sum, b_n = (by_day[c].to_list() for c in ("a_sum", "a_n", "b_sum", "b_n"))
    ci = two_group_diff_ci(
        a_sum,
        a_n,
        b_sum,
        b_n,
        block=BLOCK_DAYS,
        seed=seed,
        n_boot=N_BOOT,
        empty_denominator="guard",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


def _vol10_percentile(df: pl.DataFrame) -> pl.DataFrame:
    """Trailing-365d percentile of vol10 (for compression detection).

    ``skip_nulls=True``: this is the one historical copy that drops nulls
    out of the ranking window — vol10 has 10 leading nulls — which changes
    the denominator, and returns None when the current value is null.
    """
    ranks = trailing_percentile_rank(df["vol10"].to_list(), window=365, skip_nulls=True)
    return df.with_columns(pl.Series("vol10_pct", ranks, dtype=pl.Float64))


def build_panel(store: ParquetStore) -> pl.DataFrame:
    return canonical_daily_panel(
        store,
        SYMBOLS,
        base_columns=("ret", "close"),  # ret BEFORE close: this script's order
        feature_stages=[
            [vol_excl_current(30, name="vol30"), vol_excl_current(10, name="vol10")],
        ],
        on_missing_symbol="raise",
        per_symbol_hook=lambda df: _vol10_percentile(df).with_columns(
            **{f.name: f.expr for f in (forward_return(1), forward_return(3), forward_return(7))}
        ),
        drop_nulls=("ret", "vol30", "fwd7"),
    )


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
        sig = ci_excludes_zero(lo, hi)
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
    # Count-weighted (several trigger events can share a day), summed by
    # slice rather than prefix delta, and NaN bounds when the event series is
    # shorter than one block — all three are this call site's history.
    ci = event_mean_ci(
        values["s"].to_list(),
        values["n"].to_list(),
        block=BLOCK_DAYS,
        seed=14,
        n_boot=N_BOOT,
        accumulation="slice_sum",
        short_series="error",
        nan_below=BLOCK_DAYS,
    )
    point, lo1, hi1 = ci.point, ci.low, ci.high
    bar1 = ci_above_zero(lo1)
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
    bar2 = ci_above_zero(lo2)
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
