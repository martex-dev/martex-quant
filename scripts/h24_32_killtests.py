"""Cross-sectional ranking kill-test batch: hypotheses 24-32.

    .venv/Scripts/python scripts/h24_32_killtests.py

Pre-registered in docs/hypotheses/24-32-ranking-batch.md.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore

BLOCK_DAYS = 30
N_BOOT = 5_000
MIN_COINS = 10


def mean_ci(values: list[float], seed: int) -> tuple[float, float, float]:
    """Block-bootstrap CI for the mean of a daily series (H15-21 machinery)."""
    n = len(values)

    def prefix(xs: list[float]) -> list[float]:
        out = [0.0]
        for x in xs:
            out.append(out[-1] + x)
        return out

    p = prefix(values)
    point = p[n] / n
    rng = random.Random(seed)
    n_blocks = n // BLOCK_DAYS + 1
    means = []
    for _ in range(N_BOOT):
        total = 0.0
        cnt = 0
        for _ in range(n_blocks):
            s = rng.randint(0, n - BLOCK_DAYS)
            total += p[s + BLOCK_DAYS] - p[s]
            cnt += BLOCK_DAYS
        means.append(total / cnt)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def daily_panel(store: ParquetStore, symbols: list[str]) -> pl.DataFrame:
    parts = []
    btc = (
        store.read("BTCUSDT", Interval.D1)
        .sort("timestamp")
        .select(
            pl.col("timestamp").alias("day"),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("btc_ret"),
        )
    )
    for symbol in symbols:
        try:
            df = store.read(symbol, Interval.D1).sort("timestamp")
        except FileNotFoundError:
            continue
        df = df.select(
            pl.col("timestamp").alias("day"),
            "close",
            "volume",
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("ret"),
        ).with_columns(
            r30=pl.col("close") / pl.col("close").shift(30) - 1.0,
            r90=pl.col("close") / pl.col("close").shift(90) - 1.0,
            r90skip7=pl.col("close").shift(7) / pl.col("close").shift(90) - 1.0,
            vol90=pl.col("ret").rolling_std(90),
            max365=pl.col("close").rolling_max(365),
            maxret30=pl.col("ret").rolling_max(30),
            illiq30=(pl.col("ret").abs() / (pl.col("close") * pl.col("volume"))).rolling_mean(30),
            vshock=pl.col("volume") / pl.col("volume").rolling_mean(30),
            upshare90=(pl.col("ret") > 0).cast(pl.Float64).rolling_mean(90),
            fwd7=pl.col("close").shift(-7) / pl.col("close") - 1.0,
        )
        df = df.join(btc, on="day", how="left")
        # residual momentum: beta from trailing 90d cov/var, all data <= t
        df = df.with_columns(
            cov90=(pl.col("ret") * pl.col("btc_ret")).rolling_mean(90)
            - pl.col("ret").rolling_mean(90) * pl.col("btc_ret").rolling_mean(90),
            bvar90=(pl.col("btc_ret") ** 2).rolling_mean(90)
            - pl.col("btc_ret").rolling_mean(90) ** 2,
        ).with_columns(beta=pl.col("cov90") / pl.col("bvar90"))
        df = df.with_columns(
            resmom90=(pl.col("ret") - pl.col("beta") * pl.col("btc_ret")).rolling_sum(90)
        ).with_columns(
            hi52=pl.col("close") / pl.col("max365"),
            riskadj=pl.col("r90") / pl.col("vol90"),
        )
        parts.append(df.with_columns(pl.lit(symbol).alias("symbol")))
    return pl.concat(parts)


def ranking_spread(
    panel: pl.DataFrame,
    col: str,
    seed: int,
    *,
    gate: pl.Expr | None = None,
    min_coins: int = MIN_COINS,
) -> tuple[float, float, float, int]:
    """Top-2-minus-bottom-2 fwd7 spread of a daily ranking, block-bootstrap CI."""
    p = panel.drop_nulls([col, "fwd7"])
    if gate is not None:
        p = p.filter(gate)
    spreads = []
    for _, grp in p.group_by("day", maintain_order=True):
        if grp.height < min_coins:
            continue
        g = grp.sort(col)
        bot = g.head(2)["fwd7"].mean()
        top = g.tail(2)["fwd7"].mean()
        if top is not None and bot is not None:
            spreads.append(top - bot)
    point, lo, hi = mean_ci(spreads, seed)
    return point, lo, hi, len(spreads)


def show(name: str, point: float, lo: float, hi: float, n: int, claim: str) -> None:
    sig = lo > 0 or hi < 0
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
