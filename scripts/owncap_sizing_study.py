"""Own-capital growth-optimal sizing study (docs/research/owncap-sizing.md).

    .venv/Scripts/python scripts/owncap_sizing_study.py

Descriptive sizing-policy analysis on VALIDATED streams (0 new trials,
like the phase-4 prop sims): the 43a own-capital book (rotation-stop +
crash-bounce overlay) and rotation-stop alone, run at daily-rebalanced
leverage k with financing drag on the borrowed fraction. Answers: what
does the user's >=20%/month income target cost in drawdown and ruin risk?
"""

from __future__ import annotations

import contextlib
import json
import math
from pathlib import Path

import polars as pl

from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore

BOUNCE_COST_RT = 0.0022
FINANCING_DAILY = 0.0005  # 0.05%/day on borrowed notional (~18%/yr, CFD-swap-ish)
SCALES = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
RUIN_DD = 0.90
CACHE_DIR = Path("data/tmp/h4x_streams")
SERIES = SeriesStore(Path("."))


def build_43a_returns() -> tuple[list[float], list[float]]:
    """(combined 43a daily returns, rotation-stop daily returns)."""
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    rot_stop = SERIES.read(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
    ts_dtype = rot_stop.schema["timestamp"]
    frames = {}
    for symbol in universe:
        with contextlib.suppress(FileNotFoundError):
            frames[symbol] = store.read(symbol, Interval.D1)
    btc_ret = (
        frames["BTCUSDT"]
        .sort("timestamp")
        .select(
            pl.col("timestamp").cast(ts_dtype),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("btc_ret"),
        )
    )
    alt_parts = [
        df.sort("timestamp").select(
            pl.col("timestamp").cast(ts_dtype),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("aret"),
        )
        for s, df in frames.items()
        if s != "BTCUSDT"
    ]
    alt_ew = (
        pl.concat(alt_parts)
        .drop_nulls()
        .group_by("timestamp")
        .agg(pl.col("aret").mean().alias("alt_ew_ret"))
        .sort("timestamp")
    )
    book = (
        rot_stop.select(
            "timestamp",
            pl.col("equity").pct_change().fill_null(0.0).alias("ret"),
            "exposure",
        )
        .join(btc_ret, on="timestamp", how="left")
        .join(alt_ew, on="timestamp", how="left")
        .sort("timestamp")
        .with_columns(
            trigger_prev=(pl.col("btc_ret").shift(1) < -0.03).fill_null(False),  # noqa: FBT003
            idle_prev=(1.0 - pl.col("exposure").shift(1)).clip(0.0, 1.0),
        )
        .with_columns(
            overlay_ret=pl.when(pl.col("trigger_prev"))
            .then(pl.col("idle_prev") * (pl.col("alt_ew_ret") - BOUNCE_COST_RT))
            .otherwise(0.0)
            .fill_null(0.0)
        )
        .with_columns(combined=pl.col("ret") + pl.col("overlay_ret"))
    )
    return book["combined"].to_list(), book["ret"].to_list()


def analyze(name: str, rets: list[float]) -> None:
    n = len(rets)
    years = n / 365.0
    print(f"\n=== {name} ({n}d, {years:.1f}y) ===")
    print(
        f"{'lev':>4} {'CAGR':>9} {'MDD':>7} {'ruined':>7} {'mean 30d':>9} "
        f"{'30d>=+20%':>10} {'30d<=-20%':>10} {'worst 30d':>10}"
    )
    for k in SCALES:
        lev = [k * r - (k - 1.0) * FINANCING_DAILY for r in rets]
        equity = [1.0]
        peak, mdd, ruined = 1.0, 0.0, False
        for r in lev:
            e = equity[-1] * (1.0 + r)
            e = max(e, 0.0)
            equity.append(e)
            peak = max(peak, e)
            dd = 1.0 - e / peak if peak > 0 else 1.0
            mdd = max(mdd, dd)
            if dd >= RUIN_DD or e <= 0.0:
                ruined = True
                break
        if ruined:
            print(f"{k:>4.1f} {'—':>9} {'-90%+':>7} {'RUINED':>7}  (account effectively dead)")
            continue
        cagr = equity[-1] ** (1.0 / years) - 1.0
        m30 = [
            math.prod(1.0 + r for r in lev[i : i + 30]) - 1.0 for i in range(0, len(lev) - 30, 5)
        ]
        mean30 = sum(m30) / len(m30)
        hit = sum(1 for m in m30 if m >= 0.20) / len(m30)
        blow = sum(1 for m in m30 if m <= -0.20) / len(m30)
        worst = min(m30)
        print(
            f"{k:>4.1f} {cagr:>+8.0%} {-mdd:>7.0%} {'no':>7} {mean30:>+9.1%} "
            f"{hit:>10.0%} {blow:>10.0%} {worst:>+10.0%}"
        )


def main() -> None:
    combined, rot_stop = build_43a_returns()
    print(
        f"financing assumption: {FINANCING_DAILY:.3%}/day on borrowed notional "
        f"(~{FINANCING_DAILY * 365:.0%}/yr); daily-rebalanced leverage; "
        f"ruin = {RUIN_DD:.0%} drawdown"
    )
    analyze("43a own-capital book (rotation-stop + bounce)", combined)
    analyze("rotation-stop alone", rot_stop)


if __name__ == "__main__":
    main()
