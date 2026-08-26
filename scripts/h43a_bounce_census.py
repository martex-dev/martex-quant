"""H43a bounce-day census — descriptive, 0 new ledger trials.

    .venv/Scripts/python scripts/h43a_bounce_census.py

WHAT THIS IS
------------
A census of the ALREADY-COMPUTED H43a book (rotation-stop + crash-bounce
overlay on idle cash, docs/hypotheses/43-combo-batch.md). It answers one
question, asked by the contributor proposal response
(docs/research/bounded-search-proposal-response.md §4):

    Are the daily-loss-rule breaches concentrated in a thin high-volatility
    sub-population of bounce days, or spread across the whole trigger
    distribution?

If concentrated, a conditionally-sized overlay has somewhere to live and a
bounded search over its coefficients is worth registering. If spread, there
is no feasible region and the proposal closes on feasibility.

WHY THIS COSTS 0 TRIALS
-----------------------
Same category as docs/research/owncap-sizing.md, which swept five leverage
values over this same book and declared 0 new ledger trials: it DESCRIBED a
curve and selected no operating point. This script does the same. It prints
the whole shrink-threshold curve and picks nothing from it.

The line, stated so it is not crossed by accident: the moment a threshold is
chosen because it scored best, every threshold it beat has entered a
selection set and every one of them is a trial. This script therefore
reports and stops. Choosing from its output is a separate, registrable act.

CONSTRUCTION
------------
Reproduced exactly from scripts/h43_combo_study.py rather than paraphrased:
same cached rot_stop stream, same BTC trigger (prev-day return < -3%), same
idle-cash definition, same equal-weight alt basket, same 0.22% round-trip
bounce cost. Any drift from the published 317 bounce days / 82% mean idle
is reported as a reproduction failure and nothing else is printed.

BREACH DEFINITION
-----------------
From risk_management/prop_sim._run_path: the account busts on a day when
``equity <= prev * (1 - daily_loss_pct)``, with ``equity *= 1 + r * scale``.
So at the bars' RISK_SCALE of 0.5 and the firm's 3% daily rule, a breach day
is exactly a day whose book return satisfies ``r <= -0.06``.
"""

from __future__ import annotations

import contextlib
import json
import statistics
from pathlib import Path

import polars as pl

from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore

BOUNCE_COST_RT = 0.0022
RISK_SCALE = 0.5
DAILY_LOSS_PCT = 0.03
BREACH_RET = -DAILY_LOSS_PCT / RISK_SCALE  # -0.06
VOL_LOOKBACK = 20

PUBLISHED_BOUNCE_DAYS = 317
PUBLISHED_MEAN_IDLE = 0.82

SERIES = SeriesStore(Path("."))


def build_book() -> pl.DataFrame:
    """Rebuild the H43a book exactly as scripts/h43_combo_study.py builds it."""
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

    return (
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
            .fill_null(0.0),
            # Trailing realised vol of the BASE book, known at the close before
            # the bounce day. shift(1) keeps it strictly backward-looking: this
            # is the quantity a conditional sizing rule could actually see.
            trail_vol=pl.col("ret").rolling_std(VOL_LOOKBACK).shift(1),
        )
        .with_columns(combined=pl.col("ret") + pl.col("overlay_ret"))
    )


def pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def describe(label: str, xs: list[float]) -> None:
    if not xs:
        print(f"  {label:<26} (empty)")
        return
    print(
        f"  {label:<26} n={len(xs):<5} mean={statistics.fmean(xs):+.4f} "
        f"min={min(xs):+.4f} p05={pct(xs, 0.05):+.4f} p50={pct(xs, 0.50):+.4f} "
        f"p95={pct(xs, 0.95):+.4f} max={max(xs):+.4f}"
    )


def main() -> None:
    book = build_book()
    bounce = book.filter(pl.col("trigger_prev"))
    n_bounce = bounce.height
    mean_idle = bounce["idle_prev"].mean() or 0.0

    print("=" * 78)
    print("H43a BOUNCE-DAY CENSUS — descriptive, 0 new ledger trials")
    print("=" * 78)
    print(f"\nWindow: {book.height} days, {book['timestamp'].min()} -> {book['timestamp'].max()}")
    print(f"Bounce days: {n_bounce} (published {PUBLISHED_BOUNCE_DAYS})")
    print(f"Mean idle cash deployed: {mean_idle:.0%} (published {PUBLISHED_MEAN_IDLE:.0%})")

    # Reproduce-first, same discipline as scripts/dsr_recheck.py.
    if n_bounce != PUBLISHED_BOUNCE_DAYS or abs(mean_idle - PUBLISHED_MEAN_IDLE) > 0.005:
        print("\nREPRODUCTION FAILED against the published H43a verdict.")
        print("No census figures are reported. Fix the reconstruction first.")
        return
    print("Reproduction OK — figures below are sound.\n")

    print(
        f"Breach rule: book return <= {BREACH_RET:+.0%} "
        f"({DAILY_LOSS_PCT:.0%} daily limit at RISK_SCALE {RISK_SCALE})\n"
    )

    base_all = book["ret"].to_list()
    comb_all = book["combined"].to_list()
    base_b = bounce["ret"].to_list()
    comb_b = bounce["combined"].to_list()
    over_b = bounce["overlay_ret"].to_list()

    print("--- return distributions ---")
    describe("base, all days", base_all)
    describe("combined, all days", comb_all)
    describe("base, bounce days", base_b)
    describe("combined, bounce days", comb_b)
    describe("overlay alone, bounce", over_b)

    n_base_all = sum(1 for r in base_all if r <= BREACH_RET)
    n_comb_all = sum(1 for r in comb_all if r <= BREACH_RET)
    n_base_b = sum(1 for r in base_b if r <= BREACH_RET)
    n_comb_b = sum(1 for r in comb_b if r <= BREACH_RET)

    print("\n--- breach counts ---")
    print(f"  base book, all days      : {n_base_all}")
    print(f"  combined book, all days  : {n_comb_all}   (overlay adds {n_comb_all - n_base_all})")
    print(f"  base book, bounce days   : {n_base_b}")
    print(f"  combined, bounce days    : {n_comb_b}   (overlay adds {n_comb_b - n_base_b})")
    off = n_comb_all - n_comb_b
    print(f"  combined, NON-bounce days: {off}")
    print("\n  Non-bounce breaches are untouchable by any overlay sizing rule:")
    print("  the overlay is flat on those days. They are the floor a conditional")
    print("  rule cannot get below.")

    # Concentration: are the added breaches in a thin high-vol tail?
    rows = bounce.drop_nulls("trail_vol").sort("trail_vol")
    vols = rows["trail_vol"].to_list()
    combs = rows["combined"].to_list()
    overs = rows["overlay_ret"].to_list()
    n = len(vols)
    print(f"\n--- vol conditioning ({n} bounce days with a {VOL_LOOKBACK}d trailing vol) ---")
    print("  quintile of trailing vol (low -> high), by breach count and overlay P&L:")
    for k in range(5):
        lo, hi = n * k // 5, n * (k + 1) // 5
        seg_c, seg_o = combs[lo:hi], overs[lo:hi]
        nb = sum(1 for r in seg_c if r <= BREACH_RET)
        print(
            f"    Q{k + 1}  vol [{vols[lo]:.4f}, {vols[hi - 1]:.4f}]  "
            f"n={hi - lo:<4} breaches={nb:<3} overlay_sum={sum(seg_o):+.4f} "
            f"overlay_mean={statistics.fmean(seg_o) if seg_o else 0:+.5f}"
        )

    # Descriptive counterfactual curve. Published whole; NOTHING selected.
    print("\n--- shrink-threshold curve (DESCRIPTIVE — no threshold is chosen) ---")
    print("  'zero the overlay on the top X% of bounce days by trailing vol':")
    print(f"  {'X%':>5}  {'breaches_left':>13}  {'overlay_P&L_kept':>16}  {'% of P&L kept':>14}")
    total_overlay = sum(overs)
    for x in (0, 5, 10, 20, 30, 40, 50, 75, 100):
        cut = n - (n * x // 100)
        kept_o = overs[:cut]
        kept_c = combs[:cut] + [c - o for c, o in zip(combs[cut:], overs[cut:], strict=True)]
        nb = sum(1 for r in kept_c if r <= BREACH_RET)
        share = (sum(kept_o) / total_overlay * 100.0) if total_overlay else 0.0
        print(f"  {x:>5}  {nb:>13}  {sum(kept_o):>16.4f}  {share:>13.1f}%")

    # The symmetric arm. A census that only looks in the direction the
    # proposal assumed would be a biased census, so both directions are
    # printed. Neither is advanced as a candidate.
    print("\n  ...and the SYMMETRIC arm, 'zero the overlay on the BOTTOM X% by vol':")
    print(f"  {'X%':>5}  {'breaches_left':>13}  {'overlay_P&L_kept':>16}  {'% of P&L kept':>14}")
    for x in (0, 5, 10, 20, 30, 40, 50, 75, 100):
        cut = n * x // 100
        kept_o = overs[cut:]
        kept_c = [c - o for c, o in zip(combs[:cut], overs[:cut], strict=True)] + combs[cut:]
        nb = sum(1 for r in kept_c if r <= BREACH_RET)
        share = (sum(kept_o) / total_overlay * 100.0) if total_overlay else 0.0
        print(f"  {x:>5}  {nb:>13}  {sum(kept_o):>16.4f}  {share:>13.1f}%")

    # Quantify the (non-)relationship the proposal's functional form assumes.
    breach_flag = [1.0 if c <= BREACH_RET else 0.0 for c in combs]
    vs = pl.Series(vols)
    corr_breach = (
        pl.Series(breach_flag)
        .cast(pl.Float64)
        .to_frame("b")
        .with_columns(v=vs)
        .select(pl.corr("b", "v"))
        .item()
    )
    corr_pnl = pl.Series(overs).to_frame("o").with_columns(v=vs).select(pl.corr("o", "v")).item()
    print("\n--- the relationship the proposal's f(trailing_vol) depends on ---")
    print(f"  corr(trailing_vol, breach indicator) = {corr_breach:+.4f}")
    print(f"  corr(trailing_vol, overlay P&L)      = {corr_pnl:+.4f}")

    print("\n  Read these as trade-off tables, not menus. Picking the row that")
    print("  scores best is a selection over the candidates it beat, and costs")
    print("  that many trials; see mi-trial-accounting-design.md §2 amendment 10.")
    print("=" * 78)


if __name__ == "__main__":
    main()
