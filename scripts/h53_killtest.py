"""H53 kill test: aggressor imbalance (taker-buy ratio), 15m Binance USDM.

    .venv/Scripts/python scripts/h53_killtest.py

Pre-registered in docs/hypotheses/52-57-intraday-frontier.md.
H54 (OI divergence) is DATA-BLOCKED: Bybit serves only ~200h of OI
history; deep positioning history is paid data. Recorded as blocked.
"""

from __future__ import annotations

import random
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
DATA = Path("data/intraday")
BLOCK_DAYS = 30
N_BOOT = 5_000


def event_mean_ci(panel: pl.DataFrame, seed: int) -> tuple[float, float, float, int]:
    by_day = panel.group_by("day").agg(v_sum=pl.col("v").sum(), v_n=pl.col("v").count()).sort("day")

    def prefix(xs: list[float]) -> list[float]:
        out = [0.0]
        for x in xs:
            out.append(out[-1] + float(x))
        return out

    ps, pn = prefix(by_day["v_sum"].to_list()), prefix(by_day["v_n"].to_list())
    n = by_day.height
    point = ps[n] / max(pn[n], 1.0)
    rng = random.Random(seed)
    n_blocks = n // BLOCK_DAYS + 1
    means = []
    for _ in range(N_BOOT):
        total = cnt = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, max(n - BLOCK_DAYS, 0))
            e = s + BLOCK_DAYS
            total += ps[e] - ps[s]
            cnt += pn[e] - pn[s]
        if cnt > 0:
            means.append(total / cnt)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))], int(pn[n])


def main() -> None:
    parts = []
    for symbol in SYMBOLS:
        df = (
            pl.read_parquet(DATA / f"{symbol}_tb15m.parquet")
            .sort("ts")
            .with_columns(day=pl.col("ts").dt.date())
        )
        df = df.filter(pl.col("volume") > 0).with_columns(
            imb=(pl.col("taker_buy") / pl.col("volume") - 0.5).rolling_mean(4)
        )
        df = df.with_columns(
            mu=pl.col("imb").rolling_mean(96).shift(1),
            sd=pl.col("imb").rolling_std(96).shift(1),
            fwd1h=pl.col("close").shift(-4) / pl.col("close") - 1.0,
        ).drop_nulls(["mu", "sd", "fwd1h"])
        df = df.with_columns(z=(pl.col("imb") - pl.col("mu")) / pl.col("sd"))
        events = df.filter(pl.col("z").abs() > 2.0)
        parts.append(
            events.select(
                "day",
                v=pl.when(pl.col("z") > 0).then(pl.col("fwd1h")).otherwise(-pl.col("fwd1h")),
            )
        )
    panel = pl.concat(parts)
    point, lo, hi, n = event_mean_ci(panel, 5310)
    sig = lo > 0 or hi < 0
    print(
        f"H53 aggressor imbalance |z|>2 -> next 1h signed: n={n}  {point:+.4%}  "
        f"CI [{lo:+.4%}, {hi:+.4%}]  {'SIGNAL' if sig else 'noise'} "
        f"(continuation>0 / contrarian<0; maker toll ~0.04% RT)"
    )


if __name__ == "__main__":
    main()
