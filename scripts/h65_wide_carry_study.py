"""H65: wide-universe carry, against its pre-registered gates.

    .venv/Scripts/python scripts/h65_wide_carry_study.py

Pre-registered in docs/hypotheses/65-wide-universe-carry.md, committed
2026-08-27 BEFORE this script was written.

ALL THREE CELLS ARE REPORTED regardless of outcome: +3 trials -> 144.

The 8-symbol incumbent is recomputed HERE, in union mode, over the SHARED
window. Its figures will not match H63's published 2.29/+4.51% because the
window differs -- the registration says so. Importing published numbers
across windows is the FU-B1 defect (graveyard-audit 2.1).
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from martex_quant.backtesting.carry import CarryConfig, build_symbol_frame, run_carry
from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.stats.bootstrap import daily_mean_ci

ROOT = Path(".")
N_TRIALS = 144
SEED = 20260827
N_BOOT = 2_000
BLOCK = 30
GRID_L = (7, 30, 90)
PRIMARY_L = 30

GATE_A_MIN_CAGR = 2.0
GATE_A_MIN_SHARPE = 1.0
GATE_A_DSR = 0.95
GATE_C_MAX_CORR = 0.30

INCUMBENT_8 = (
    "ADAUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "DOGEUSDT",
    "ETHUSDT",
    "LTCUSDT",
    "SOLUSDT",
    "XRPUSDT",
)

WIDE = CarryConfig(require_all_symbols=False)


def load_frames() -> dict[str, pl.DataFrame]:
    """Every universe symbol with all three of spot, perp and funding."""
    store = ParquetStore(ROOT / "data/lake")
    symbols = json.loads((ROOT / "config/universe.json").read_text(encoding="utf-8"))["symbols"]
    frames: dict[str, pl.DataFrame] = {}
    for symbol in symbols:
        f_path = ROOT / f"data/funding/{symbol}.parquet"
        p_path = ROOT / f"data/perp/{symbol}.parquet"
        if not (f_path.exists() and p_path.exists()):
            continue
        try:
            spot = store.read(symbol, Interval.D1)
        except FileNotFoundError:
            continue
        built = build_symbol_frame(spot, pl.read_parquet(p_path), pl.read_parquet(f_path))
        if built.height >= 60:
            frames[symbol] = built
    return frames


def with_filter(frames: dict[str, pl.DataFrame], lookback: int) -> dict[str, pl.DataFrame]:
    return {
        symbol: frame.with_columns(
            hold=(pl.col("funding").rolling_mean(lookback).shift(1) > 0.0).fill_null(value=False)
        )
        for symbol, frame in frames.items()
    }


def clip_to(daily: pl.DataFrame, lo: object, hi: object) -> pl.DataFrame:
    return daily.filter((pl.col("timestamp") >= lo) & (pl.col("timestamp") <= hi))


def evaluate(daily: pl.DataFrame) -> dict[str, float]:
    rets = daily["ret"].to_list()
    equity_curve = daily.with_columns(eq=(1.0 + pl.col("ret")).cum_prod() * 10_000.0).select(
        "timestamp", pl.col("eq").alias("equity"), pl.lit(1.0).alias("exposure")
    )
    metrics = compute_metrics(equity_curve, [], Interval.D1)
    ci = daily_mean_ci(
        rets,
        block=BLOCK,
        seed=SEED,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    series = pl.Series(rets)
    skew, kurt = series.skew(), series.kurtosis()
    dsr = probabilistic_sharpe_ratio(
        (sum(rets) / len(rets)) / (series.std() or 1.0),
        n_obs=len(rets),
        skew=float(skew) if skew is not None else 0.0,
        kurtosis=(float(kurt) + 3.0) if kurt is not None else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, float(series.var() or 0.0)),
    )
    return {
        "cagr": metrics.cagr_pct,
        "sharpe": metrics.sharpe,
        "mdd": metrics.max_drawdown_pct,
        "ci_low": ci.low,
        "ci_point": ci.point,
        "dsr": dsr,
        "n_days": float(daily.height),
        "mean_symbols": float(daily["n_symbols"].mean() or 0.0),
    }


def main() -> None:
    frames = load_frames()
    wide_symbols = sorted(frames)
    incumbent_frames = {s: f for s, f in frames.items() if s in INCUMBENT_8}

    print("=" * 78)
    print("H65 — WIDE-UNIVERSE CARRY (3 cells, trials 142-144 -> 144)")
    print("=" * 78)
    print(f"\nWide universe: {len(wide_symbols)} symbols with spot + perp + funding")
    print(f"  {', '.join(s.removesuffix('USDT') for s in wide_symbols)}")
    print(f"Incumbent: {len(incumbent_frames)} majors, re-run in union mode on the shared window\n")

    # Shared window: where BOTH books have data.
    wide_run = run_carry(with_filter(frames, PRIMARY_L), WIDE)
    inc_run = run_carry(with_filter(incumbent_frames, PRIMARY_L), WIDE)
    lo = max(wide_run.daily["timestamp"].min(), inc_run.daily["timestamp"].min())
    hi = min(wide_run.daily["timestamp"].max(), inc_run.daily["timestamp"].max())
    print(f"Shared comparison window: {str(lo)[:10]} -> {str(hi)[:10]}")

    inc = evaluate(clip_to(inc_run.daily, lo, hi))
    print(
        f"\nIncumbent (8 majors, L=30, THIS window): Sharpe {inc['sharpe']:.2f}   "
        f"CAGR {inc['cagr']:+.2f}%   MDD {inc['mdd']:.2f}%"
    )
    print("  (differs from H63's published 2.29 / +4.51% because the window differs")
    print("   -- see the pre-registration; this is the like-for-like comparison)")

    results: dict[int, dict[str, float]] = {}
    print("\n--- the declared 3-cell grid (ALL cells reported) ---")
    for lookback in GRID_L:
        run = run_carry(with_filter(frames, lookback), WIDE)
        got = evaluate(clip_to(run.daily, lo, hi))
        results[lookback] = got
        star = " (PRIMARY)" if lookback == PRIMARY_L else ""
        print(f"\n  L={lookback}{star}")
        print(
            f"    Sharpe {got['sharpe']:6.2f}   CAGR {got['cagr']:+7.2f}%   "
            f"MDD {got['mdd']:6.2f}%   DSR {got['dsr']:.4f}"
        )
        print(
            f"    mean {got['ci_point'] * 1e4:+.3f}bp/day "
            f"CI low {got['ci_low'] * 1e4:+.3f}bp   "
            f"avg symbols held-eligible {got['mean_symbols']:.1f}"
        )

    p = results[PRIMARY_L]
    wide_clipped = clip_to(wide_run.daily, lo, hi)

    rot = SeriesStore(ROOT).read(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
    rot_ret = (
        rot.sort("timestamp")
        .select(
            pl.col("timestamp").cast(pl.Datetime("us", "UTC")).dt.truncate("1d"),
            pl.col("equity").pct_change().fill_null(0.0).alias("rot_ret"),
        )
        .group_by("timestamp")
        .agg(pl.col("rot_ret").last())
    )
    joined = (
        wide_clipped.select(pl.col("timestamp").dt.truncate("1d"), pl.col("ret").alias("mine"))
        .join(rot_ret, on="timestamp", how="inner")
        .drop_nulls()
    )
    corr = (
        float(joined.select(pl.corr("mine", "rot_ret")).item())
        if joined.height >= 30
        else float("nan")
    )

    print("\n--- symbol count over time (the ragged-history caveat, 7) ---")
    by_year = wide_clipped.with_columns(y=pl.col("timestamp").dt.year())
    for year, group in sorted(by_year.group_by("y"), key=lambda kv: kv[0]):
        net = group["ret"].sum() / (group.height / 365.25) * 100.0
        print(f"    {year[0]}  symbols~{group['n_symbols'].mean():5.1f}  net {net:+7.2f}%/yr")

    print("\n" + "-" * 78)
    print("GATES (primary cell L=30)")
    print("-" * 78)
    a1 = p["ci_low"] > 0.0
    a2 = p["cagr"] >= GATE_A_MIN_CAGR
    a3 = p["sharpe"] >= GATE_A_MIN_SHARPE
    a4 = p["dsr"] >= GATE_A_DSR
    b5 = p["sharpe"] > inc["sharpe"]
    b6 = p["cagr"] > inc["cagr"]
    c7 = abs(corr) < GATE_C_MAX_CORR

    def mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    print(f"  A1 CI excludes zero        : {p['ci_low'] * 1e4:+.3f}bp  {mark(a1)}")
    print(f"  A2 CAGR >= {GATE_A_MIN_CAGR:.0f}%/yr          : {p['cagr']:+.2f}%  {mark(a2)}")
    print(f"  A3 Sharpe >= {GATE_A_MIN_SHARPE:.1f}           : {p['sharpe']:.2f}  {mark(a3)}")
    print(f"  A4 DSR >= {GATE_A_DSR:.2f} @ {N_TRIALS}     : {p['dsr']:.4f}  {mark(a4)}")
    print(f"  B5 Sharpe > {inc['sharpe']:.2f} (8-sym)   : {p['sharpe']:.2f}  {mark(b5)}")
    print(f"  B6 CAGR > {inc['cagr']:+.2f}% (8-sym)   : {p['cagr']:+.2f}%  {mark(b6)}")
    print(
        f"  C7 |corr| rot-stop < {GATE_C_MAX_CORR:.2f}   : "
        f"{corr:+.4f} (n={joined.height})  {mark(c7)}"
    )

    gate_a, gate_b, gate_c = a1 and a2 and a3 and a4, b5 and b6, c7
    print("\n" + "=" * 78)
    if gate_a and gate_b and gate_c:
        print("VERDICT: A + B + C PASS -> breadth helps; replaces H63 as the carry spec.")
    elif gate_a and gate_c:
        print("VERDICT: STANDALONE-VIABLE — real, but breadth did NOT help.")
        print("H63's 8-symbol spec remains the carry spec. Meta-finding 3 does not")
        print("extend to carry. Per docs/research/standalone-viable-amendment.md.")
    else:
        print("VERDICT: KILLED — the carry premium on 8 majors does not generalize.")
    print("=" * 78)

    out = ROOT / "data/tmp/h65_carry"
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(
        json.dumps(
            {
                "wide_symbols": wide_symbols,
                "incumbent": inc,
                "grid": {str(k): v for k, v in results.items()},
                "corr_rotation_stop": corr,
                "gate_a": gate_a,
                "gate_b": gate_b,
                "gate_c": gate_c,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
