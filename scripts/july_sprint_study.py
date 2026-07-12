"""July-sprint deadline study (docs/research/july-sprint.md).

    .venv/Scripts/python scripts/july_sprint_study.py

Deadline-constrained policy analysis on VALIDATED streams (0 new ledger
trials): the user's goal is eval pass + ~$500 gross funded profit
(~$400 at an assumed 80% split) before July 31. With a deadline, the
objective changes from P(pass ever) to P(chain complete by day D) —
busting fast and retrying becomes part of the strategy, so higher
sizing can dominate. This script measures that honestly.

Chain model per Monte Carlo path (block bootstrap, EOD checks):
  1. Eval attempts (fee each): 5k, target +10%, static floor -6%,
     daily loss 3%. Bust -> retry next day (max attempts budget).
  2. On pass: funded account starts next day, same limits; chain
     succeeds when funded equity reaches +10% (~$500 gross) by day D.
All results are UPPER bounds (EOD rule checks; instant retry/activation
assumed — real firms take 1-3 days between stages).
"""

from __future__ import annotations

import contextlib
import json
import random
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore

FEE = 51.80
ACCOUNT = 5_000.0
TARGET_PCT = 0.10
STATIC_FLOOR_PCT = 0.06
DAILY_LOSS_PCT = 0.03
BLOCK = 7
N_PATHS = 20_000
DEADLINES = [17, 12, 6]  # buy now / after 1 more shakedown week / at the gate
SCALES = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
MAX_ATTEMPTS = 3
BOUNCE_COST_RT = 0.0022
CACHE_DIR = Path("data/tmp/h4x_streams")


def build_streams() -> dict[str, list[float]]:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    rot_stop = pl.read_parquet(CACHE_DIR / "rot_stop_stream.parquet")
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
    return {
        "rotation-stop": book["ret"].to_list(),
        "43a book (rot-stop+bounce)": book["combined"].to_list(),
    }


def run_chain(
    rets: list[float], scale: float, deadline: int, rng: random.Random
) -> tuple[bool, bool, int]:
    """One path: (chain_success, eval_passed, fees_paid)."""
    max_start = len(rets) - BLOCK
    day = 0
    fees = 0
    attempt = 0
    while attempt < MAX_ATTEMPTS and day < deadline:
        attempt += 1
        fees += 1
        equity = ACCOUNT
        floor = ACCOUNT * (1.0 - STATIC_FLOOR_PCT)
        target = ACCOUNT * (1.0 + TARGET_PCT)
        passed = False
        busted = False
        while day < deadline and not passed and not busted:
            start = rng.randint(0, max_start)
            for r in rets[start : start + BLOCK]:
                day += 1
                prev = equity
                equity *= 1.0 + r * scale
                if equity <= prev * (1.0 - DAILY_LOSS_PCT) or equity <= floor:
                    busted = True
                    break
                if equity >= target:
                    passed = True
                    break
                if day >= deadline:
                    break
        if busted:
            continue  # retry with a fresh fee
        if not passed:
            return (False, False, fees)  # deadline hit mid-attempt
        # Funded stage: same limits, need +10% (~$500 gross) by the deadline.
        equity = ACCOUNT
        floor = ACCOUNT * (1.0 - STATIC_FLOOR_PCT)
        target = ACCOUNT * (1.0 + TARGET_PCT)
        while day < deadline:
            start = rng.randint(0, max_start)
            for r in rets[start : start + BLOCK]:
                day += 1
                prev = equity
                equity *= 1.0 + r * scale
                if equity <= prev * (1.0 - DAILY_LOSS_PCT) or equity <= floor:
                    return (False, True, fees)  # funded account busted
                if equity >= target:
                    return (True, True, fees)
                if day >= deadline:
                    break
        return (False, True, fees)  # passed eval, profit incomplete
    return (False, False, fees)


def main() -> None:
    streams = build_streams()
    print(
        f"chain: eval (+10%, -6% floor, 3% daily) -> funded (+10% profit), "
        f"retries up to {MAX_ATTEMPTS} fees, {N_PATHS} paths, EOD checks (upper bounds)\n"
    )
    for name, rets in streams.items():
        print(f"=== engine: {name} ===")
        print(
            f"{'deadline':>9} {'scale':>6} {'P(chain)':>9} {'P(pass eval)':>13} "
            f"{'avg fees':>9} {'fee cost':>9}"
        )
        for deadline in DEADLINES:
            best = None
            for scale in SCALES:
                rng = random.Random(int(scale * 100) + deadline * 7)
                chain = passed = fees_total = 0
                for _ in range(N_PATHS):
                    ok, p, fees = run_chain(rets, scale, deadline, rng)
                    chain += ok
                    passed += p
                    fees_total += fees
                row = (
                    deadline,
                    scale,
                    chain / N_PATHS,
                    passed / N_PATHS,
                    fees_total / N_PATHS,
                    fees_total / N_PATHS * FEE,
                )
                if best is None or row[2] > best[2]:
                    best = row
                print(
                    f"{row[0]:>8}d {row[1]:>5.1f}x {row[2]:>9.1%} {row[3]:>13.1%} "
                    f"{row[4]:>9.2f} {row[5]:>8.0f}$"
                )
            assert best is not None
            print(
                f"  -> best at {best[0]}d: {best[1]:.1f}x, P(chain) {best[2]:.1%}, "
                f"P(eval pass) {best[3]:.1%}\n"
            )


if __name__ == "__main__":
    main()
