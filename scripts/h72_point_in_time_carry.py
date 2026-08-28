"""H72: does carry survive a universe chosen without hindsight?

    .venv/Scripts/python scripts/h72_point_in_time_carry.py

Pre-registered in docs/hypotheses/72-point-in-time-carry.md, committed
2026-08-28 BEFORE this script was written (commit 18ed853). The pool, the
selection rule, the H63 spec, the cells and all four bars are fixed by
that document. The STRATEGY is not varied at all -- only which symbols it
may hold.

Trials 173-174 (reselection cadence 90d and 365d).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from martex_quant.backtesting.carry import CarryConfig, build_symbol_frame, run_carry
from martex_quant.backtesting.metrics import (
    Metrics,
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.data.models import Interval
from martex_quant.features.universe import UniverseSchedule, point_in_time_universes
from martex_quant.stats.bootstrap import CI, daily_mean_ci

ROOT = Path(".")
SPOT_POOL = ROOT / "data/pool"
PERP_POOL = ROOT / "data/perp_pool"
FUNDING_POOL = ROOT / "data/funding_pool"

# ---------------------------------------------------------------- FIXED BY
# THE PRE-REGISTRATION (docs/hypotheses/72-point-in-time-carry.md).
# Do not edit any constant below to chase a result.
UNIVERSE_SIZE = 40
VOLUME_WINDOW = 30
MIN_HISTORY = 90
CELLS = (90, 365)
PRIMARY_CELL = 90

FILTER_L = 30  # H63's trailing-funding filter, the deployed carry spec
CONFIG = CarryConfig(require_all_symbols=False)

WINDOW_END = dt.datetime(2026, 7, 9, tzinfo=dt.UTC)
N_TRIALS = 174
SEED = 20260828
N_BOOT = 2_000
BLOCK = 30

BAR_MIN_SHARPE = 1.0
BAR_DSR = 0.95
BAR_SHARPE_FRACTION = 0.70  # Gate B, the SAME tolerance H71 used
MAJORS = ("ADAUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT")
# --------------------------------------------------------------------------


def load_pool() -> tuple[dict[str, pl.DataFrame], dict[str, pl.DataFrame]]:
    """(carry frames, perp-volume frames) for every symbol with all three legs."""
    frames: dict[str, pl.DataFrame] = {}
    volume: dict[str, pl.DataFrame] = {}
    for perp_path in sorted(PERP_POOL.glob("*.parquet")):
        symbol = perp_path.stem
        spot_path = SPOT_POOL / f"{symbol}.parquet"
        funding_path = FUNDING_POOL / f"{symbol}.parquet"
        if not spot_path.exists() or not funding_path.exists():
            continue
        spot = (
            pl.read_parquet(spot_path)
            .filter(pl.col("timestamp") <= WINDOW_END)
            .select("timestamp", "close")
        )
        perp_raw = pl.read_parquet(perp_path).filter(pl.col("day") <= WINDOW_END)
        funding = (
            pl.read_parquet(funding_path)
            .filter(pl.col("timestamp") <= WINDOW_END)
            .select("timestamp", "rate")
        )
        if spot.height < MIN_HISTORY or perp_raw.height < MIN_HISTORY or funding.height < 10:
            continue
        frame = build_symbol_frame(spot, perp_raw.select("day", "perp_close"), funding)
        if frame.height < MIN_HISTORY:
            continue
        frames[symbol] = frame
        volume[symbol] = perp_raw.select(pl.col("day").alias("timestamp"), pl.col("quote_volume"))
    return frames, volume


def gated(
    frames: dict[str, pl.DataFrame],
    schedule: UniverseSchedule | None,
) -> dict[str, pl.DataFrame]:
    """H63's trailing-funding filter, optionally ANDed with the day's universe.

    ``shift(1)`` after the rolling mean is what keeps the funding filter
    strictly backward-looking -- day t's decision may not see day t's
    funding. It is copied verbatim from scripts/h63_conditional_carry_study.py
    so the deployed spec is reproduced rather than re-implemented.

    The universe mask is a second gate on the same ``hold`` column, so a
    symbol is held only when its funding is paying AND it was selectable
    that day. Every universe entry is dated at or before the day it gates.
    """
    out: dict[str, pl.DataFrame] = {}
    for symbol, frame in frames.items():
        held = (pl.col("funding").rolling_mean(FILTER_L).shift(1) > 0.0).fill_null(value=False)
        gated_frame = frame.with_columns(hold=held)
        if schedule is not None:
            allowed = [
                symbol in schedule.for_date(ts.date()) for ts in gated_frame["day"].to_list()
            ]
            gated_frame = gated_frame.with_columns(
                hold=pl.col("hold") & pl.Series("in_universe", allowed, dtype=pl.Boolean)
            )
        out[symbol] = gated_frame
    return out


def evaluate(
    daily: pl.DataFrame, equity: pl.DataFrame, variance: float
) -> tuple[Metrics, CI, float]:
    rets = daily["ret"]
    metrics = compute_metrics(equity, [], Interval.D1)
    ci = daily_mean_ci(
        rets.to_list(),
        block=BLOCK,
        seed=SEED,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    pp = (rets.mean() or 0.0) / (rets.std() or 1.0)
    skew, kurt = rets.skew(), rets.kurtosis()
    dsr = probabilistic_sharpe_ratio(
        pp,
        n_obs=rets.len(),
        skew=float(skew) if skew is not None else 0.0,
        kurtosis=(float(kurt) + 3.0) if kurt is not None else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, variance),
    )
    return metrics, ci, dsr


def main() -> None:
    print("=" * 104)
    print("H72 - POINT-IN-TIME CARRY: does the last validated edge survive? (trials 173-174)")
    print("=" * 104)

    frames, volume = load_pool()
    universe_symbols = set(
        json.loads((ROOT / "config/universe.json").read_text(encoding="utf-8"))["symbols"]
    )
    hindsight = {s: f for s, f in frames.items() if s in universe_symbols}
    majors = {s: f for s, f in frames.items() if s in MAJORS}
    print(
        f"\nEligible (spot + perp + funding): {len(frames)} symbols. "
        f"Hindsight universe present: {len(hindsight)}. Majors present: {len(majors)}."
    )

    # build_symbol_frame keys its output on "day", not "timestamp".
    starts = [f["day"].min() for f in frames.values()]
    start = min(starts) + dt.timedelta(days=MIN_HISTORY)
    schedules = {
        cadence: point_in_time_universes(
            volume,
            size=UNIVERSE_SIZE,
            volume_window=VOLUME_WINDOW,
            min_history=MIN_HISTORY,
            reselect_every=cadence,
            start=start,
            end=WINDOW_END,
        )
        for cadence in CELLS
    }

    primary_schedule = schedules[PRIMARY_CELL]
    print("\n--- Section 5.2 diagnostic: overlap with the hindsight universe ---")
    print(f"    {'date':12}{'rankable':>10}{'overlap':>28}")
    for when, symbols in [e for i, e in enumerate(primary_schedule.entries) if i % 4 == 0]:
        overlap = len(symbols & universe_symbols)
        print(
            f"    {str(when):12}{len(symbols):>10}"
            f"{overlap:>18} / {len(universe_symbols)} ({overlap / len(universe_symbols):>5.0%})"
        )

    print("\n--- running the books ---")
    books: dict[str, pl.DataFrame] = {}
    equities: dict[str, pl.DataFrame] = {}
    runs = {
        "hindsight wide (H65)": (hindsight, None),
        "hindsight 8 majors (H63)": (majors, None),
        **{f"point-in-time {c}d": (frames, schedules[c]) for c in CELLS},
    }
    for label, (source, schedule) in runs.items():
        result = run_carry(gated(source, schedule), CONFIG)
        books[label] = result.daily.select("timestamp", "ret")
        equities[label] = result.equity
        print(f"  {label:28} n_symbols={result.n_symbols:>3}  n_days={result.n_days}")

    common = None
    for label, daily in books.items():
        piece = daily.rename({"ret": label})
        common = piece if common is None else common.join(piece, on="timestamp", how="inner")
    assert common is not None
    common = common.sort("timestamp")
    labels = list(books)
    pps = [(common[c].mean() or 0.0) / (common[c].std() or 1.0) for c in labels]
    variance = float(pl.Series(pps).var() or 0.0)

    stated: dict[str, tuple[Metrics, CI, float]] = {}
    for label in labels:
        rets = common.select("timestamp", pl.col(label).alias("ret"))
        equity = rets.select(
            "timestamp",
            (1.0 + pl.col("ret")).cum_prod().alias("equity"),
            pl.lit(1.0).alias("exposure"),
        )
        stated[label] = evaluate(rets, equity, variance)

    print(
        f"\n--- the cells, identical window ({common.height} days, "
        f"{str(common['timestamp'].min())[:10]} -> {str(common['timestamp'].max())[:10]}) ---"
    )
    print(
        f"  {'book':30}{'CAGR':>9}{'Sharpe':>9}{'MDD':>9}"
        f"{'mean bp/day':>13}{'95% CI (bp)':>22}{'DSR':>8}"
    )
    for label in labels:
        metrics, ci, dsr = stated[label]
        mark = "  <- PRIMARY" if label == f"point-in-time {PRIMARY_CELL}d" else ""
        print(
            f"  {label:30}{metrics.cagr_pct:>8.2f}%{metrics.sharpe:>9.2f}"
            f"{metrics.max_drawdown_pct:>8.2f}%{ci.point * 1e4:>13.3f}"
            f"{'[' + f'{ci.low * 1e4:+.3f}, {ci.high * 1e4:+.3f}' + ']':>22}{dsr:>8.4f}{mark}"
        )

    wide_m, _, _ = stated["hindsight wide (H65)"]
    pri_m, pri_ci, pri_dsr = stated[f"point-in-time {PRIMARY_CELL}d"]

    print("\n--- the four pre-registered bars (Section 5) ---")

    def line(label: str, measured: str, ok: bool) -> None:
        print(f"  {label:<46} {measured:<32} -> {'PASS' if ok else 'FAIL'}")

    a1 = pri_m.sharpe >= BAR_MIN_SHARPE
    a2 = pri_ci.low > 0.0
    a3 = pri_dsr >= BAR_DSR
    b4 = pri_m.sharpe >= wide_m.sharpe * BAR_SHARPE_FRACTION
    line(f"A1. Sharpe >= {BAR_MIN_SHARPE:.1f}", f"{pri_m.sharpe:.2f}", a1)
    line(
        "A2. mean daily net > 0, CI excludes zero",
        f"{pri_ci.point * 1e4:+.3f}bp, low {pri_ci.low * 1e4:+.3f}bp",
        a2,
    )
    line(f"A3. DSR_global >= {BAR_DSR:.2f} @ {N_TRIALS}", f"{pri_dsr:.4f}", a3)
    line(
        f"B4. Sharpe >= {BAR_SHARPE_FRACTION:.0%} of H65 wide's",
        f"{pri_m.sharpe:.2f} vs {wide_m.sharpe * BAR_SHARPE_FRACTION:.2f} needed",
        b4,
    )
    print(
        f"\n  Gate A {'PASS' if a1 and a2 and a3 else 'FAIL'}   Gate B {'PASS' if b4 else 'FAIL'}"
    )
    retention = pri_m.sharpe / wide_m.sharpe if wide_m.sharpe else float("nan")
    print(
        f"  Sharpe retained: {retention:.0%} of the hindsight wide book's "
        f"({pri_m.sharpe:.2f} vs {wide_m.sharpe:.2f})   "
        f"-- momentum retained 58% (H71)"
    )

    print("\n--- Section 5.1: were the predictions right? ---")
    print(f"  predicted Gate A passes: {'RIGHT' if a1 and a2 and a3 else 'WRONG'}")
    print(f"  predicted Gate B passes: {'RIGHT' if b4 else 'WRONG'}")
    print(
        f"  predicted retention materially above momentum's 58%: "
        f"{retention:.0%}  -> {'RIGHT' if retention > 0.58 else 'WRONG'}"
    )

    print("\n--- reported, not gated: per-year ---")
    by_year = common.with_columns(year=pl.col("timestamp").dt.year())
    header = f"  {'year':6}{'n':>6}" + "".join(f"{lab[:14]:>16}" for lab in labels)
    print(header)
    for year, group in sorted(by_year.group_by("year"), key=lambda kv: kv[0]):
        n = group.height
        cells = "".join(f"{group[lab].sum() / (n / 365.25) * 100.0:>15.2f}%" for lab in labels)
        print(f"  {year[0]:<6}{n:>6}{cells}")

    print("\n  RECENT REGIME (carried forward, Section 5.2): H62, H63 and H65 each found")
    print("  carry earning ~nothing in 2025-2026. Nothing in this hypothesis addresses that.")
    print("\n" + "=" * 104)


if __name__ == "__main__":
    main()
