"""Cross-sectional ranking kill-test batch: hypotheses 24-32.

    .venv/Scripts/python scripts/h24_32_killtests.py

Pre-registered in docs/hypotheses/24-32-ranking-batch.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.features.cross_section import ranking_spread_series
from trading_bot.features.panel import (
    amihud_illiquidity,
    forward_return,
    momentum,
    momentum_skip,
    rolling_max_close,
    rolling_max_return,
    up_day_share,
    vol_incl_current,
    volume_shock,
)
from trading_bot.features.panel import daily_panel as canonical_daily_panel
from trading_bot.stats.bootstrap import daily_mean_ci
from trading_bot.stats.significance import ci_excludes_zero

BLOCK_DAYS = 30
N_BOOT = 5_000
MIN_COINS = 10


def mean_ci(values: list[float], seed: int) -> tuple[float, float, float]:
    """Unweighted block-bootstrap CI for the mean of a daily series
    (one top2-minus-bottom2 spread per day)."""
    ci = daily_mean_ci(
        values,
        block=BLOCK_DAYS,
        seed=seed,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


def _residual_momentum(df: pl.DataFrame, btc: pl.DataFrame) -> pl.DataFrame:
    """Cross-symbol stage: join BTC's return, then beta and residual momentum.

    A left join plus four dependent with_columns calls — not a per-symbol
    expression, so it stays here as a hook rather than becoming a Feature.
    """
    df = df.join(btc, on="day", how="left")
    # residual momentum: beta from trailing 90d cov/var, all data <= t
    df = df.with_columns(
        cov90=(pl.col("ret") * pl.col("btc_ret")).rolling_mean(90)
        - pl.col("ret").rolling_mean(90) * pl.col("btc_ret").rolling_mean(90),
        bvar90=(pl.col("btc_ret") ** 2).rolling_mean(90) - pl.col("btc_ret").rolling_mean(90) ** 2,
    ).with_columns(beta=pl.col("cov90") / pl.col("bvar90"))
    return df.with_columns(
        resmom90=(pl.col("ret") - pl.col("beta") * pl.col("btc_ret")).rolling_sum(90)
    ).with_columns(
        hi52=pl.col("close") / pl.col("max365"),
        riskadj=pl.col("r90") / pl.col("vol90"),
    )


def daily_panel(store: ParquetStore, symbols: list[str]) -> pl.DataFrame:
    btc = (
        store.read("BTCUSDT", Interval.D1)
        .sort("timestamp")
        .select(
            pl.col("timestamp").alias("day"),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("btc_ret"),
        )
    )
    return canonical_daily_panel(
        store,
        symbols,
        base_columns=("close", "volume", "ret"),
        feature_stages=[
            [
                momentum(30),
                momentum(90),
                momentum_skip(90, 7),
                # INCLUDING the current bar — this script's convention, and
                # the only one in the corpus that does so. riskadj (H24) and
                # the low-vol ranking (H27) both depend on it.
                vol_incl_current(90, name="vol90"),
                rolling_max_close(365, name="max365"),
                rolling_max_return(30, name="maxret30"),
                amihud_illiquidity(30, name="illiq30"),
                volume_shock(30, name="vshock"),
                up_day_share(90, name="upshare90"),
                forward_return(7),
            ],
        ],
        on_missing_symbol="skip",
        per_symbol_hook=lambda df: _residual_momentum(df, btc),
    )


def ranking_spread(
    panel: pl.DataFrame,
    col: str,
    seed: int,
    *,
    gate: pl.Expr | None = None,
    min_coins: int = MIN_COINS,
) -> tuple[float, float, float, int]:
    """Top-2-minus-bottom-2 fwd7 spread of a daily ranking, block-bootstrap CI.

    Nulls are dropped INSIDE, before the min-symbols gate — this script's
    placement, which can drop a whole thin day rather than just a row.
    """
    spreads = ranking_spread_series(
        panel,
        col,
        outcome_column="fwd7",
        k=2,
        min_symbols=min_coins,
        gate=gate,
        drop_nulls_on=(col, "fwd7"),
    )
    point, lo, hi = mean_ci(spreads, seed)
    return point, lo, hi, len(spreads)


def show(name: str, point: float, lo: float, hi: float, n: int, claim: str) -> None:
    sig = ci_excludes_zero(lo, hi)
    print(
        f"  {name:<50} n={n:>5}  spread {point:+.3%}  CI [{lo:+.3%}, {hi:+.3%}]  "
        f"{'SIGNAL' if sig else 'noise'}  ({claim})"
    )


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    wide = daily_panel(store, universe)
    print(f"wide daily panel: {wide.height} symbol-days\n")

    print("=== references (NOT trials): deployed-family rankings ===")
    for col, seed in [("r30", 2401), ("r90", 2402)]:
        pt, lo, hi, n = ranking_spread(wide, col, seed)
        show(f"reference: rank by {col}", pt, lo, hi, n, "reference")

    print("=== H24 risk-adjusted momentum (r90/vol90) ===")
    pt, lo, hi, n = ranking_spread(wide, "riskadj", 2410)
    show("rank by r90/vol90", pt, lo, hi, n, "PASS if CI>0")

    print("=== H25 52-week-high proximity ===")
    pt, lo, hi, n = ranking_spread(wide, "hi52", 2510)
    show("rank by close/max365", pt, lo, hi, n, "PASS if CI>0")

    print("=== H26 residual momentum (BTC beta stripped, BTC excluded) ===")
    pt, lo, hi, n = ranking_spread(wide.filter(pl.col("symbol") != "BTCUSDT"), "resmom90", 2610)
    show("rank by 90d residual momentum", pt, lo, hi, n, "PASS if CI>0")

    print("=== H27 low-volatility anomaly (two-sided) ===")
    pt, lo, hi, n = ranking_spread(wide, "vol90", 2710)
    show("rank by vol90 (top2=HIGH vol)", pt, lo, hi, n, "low-vol claim = CI<0")

    print("=== H28 MAX / lottery effect (two-sided) ===")
    pt, lo, hi, n = ranking_spread(wide, "maxret30", 2810)
    show("rank by max 1d ret in 30d (top2=HIGH max)", pt, lo, hi, n, "lottery claim = CI<0")

    print("=== H29 illiquidity premium (two-sided) ===")
    pt, lo, hi, n = ranking_spread(wide, "illiq30", 2910)
    show("rank by Amihud illiq30 (top2=ILLIQUID)", pt, lo, hi, n, "illiq claim = CI>0")

    print("=== H30 volume-shock ranking (two-sided) ===")
    pt, lo, hi, n = ranking_spread(wide, "vshock", 3010)
    show("rank by volume/30d avg volume", pt, lo, hi, n, "two-sided")

    print("=== H31 trend smoothness among r90>0 coins ===")
    pt, lo, hi, n = ranking_spread(wide, "upshare90", 3110, gate=pl.col("r90") > 0, min_coins=6)
    show("rank by up-day share | r90>0", pt, lo, hi, n, "PASS if CI>0")

    print("=== H32 skip-week momentum ===")
    pt, lo, hi, n = ranking_spread(wide, "r90skip7", 3210)
    show("rank by r(90..7)", pt, lo, hi, n, "PASS if CI>0")


if __name__ == "__main__":
    main()
