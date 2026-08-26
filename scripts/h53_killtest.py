"""H53 kill test: aggressor imbalance (taker-buy ratio), 15m Binance USDM.

    .venv/Scripts/python scripts/h53_killtest.py

Pre-registered in docs/hypotheses/52-57-intraday-frontier.md.
H54 (OI divergence) is DATA-BLOCKED: Bybit serves only ~200h of OI
history; deep positioning history is paid data. Recorded as blocked.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from martex_quant.features.panel import forward_return
from martex_quant.stats.bootstrap import event_mean_ci as _event_mean_ci
from martex_quant.stats.significance import ci_excludes_zero

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
    """Count-weighted: many imbalance events land on the same day, so days
    with more events must weigh more."""
    by_day = panel.group_by("day").agg(v_sum=pl.col("v").sum(), v_n=pl.col("v").count()).sort("day")
    ci = _event_mean_ci(
        by_day["v_sum"].to_list(),
        by_day["v_n"].to_list(),
        block=BLOCK_DAYS,
        seed=seed,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="clamp",
    )
    return ci.point, ci.low, ci.high, ci.n


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
        # 4 bars of 15m = 1 hour; the name is by duration, not by bar count.
        fwd = forward_return(4, name="fwd1h")
        df = df.with_columns(
            mu=pl.col("imb").rolling_mean(96).shift(1),
            sd=pl.col("imb").rolling_std(96).shift(1),
            **{fwd.name: fwd.expr},
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
    sig = ci_excludes_zero(lo, hi)
    print(
        f"H53 aggressor imbalance |z|>2 -> next 1h signed: n={n}  {point:+.4%}  "
        f"CI [{lo:+.4%}, {hi:+.4%}]  {'SIGNAL' if sig else 'noise'} "
        f"(continuation>0 / contrarian<0; maker toll ~0.04% RT)"
    )


if __name__ == "__main__":
    main()
