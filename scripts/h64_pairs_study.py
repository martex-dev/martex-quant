"""H64: cointegrated pairs (family F4), against its pre-registered gates.

    .venv/Scripts/python scripts/h64_pairs_study.py

Pre-registered in docs/hypotheses/64-cointegration-pairs.md, committed
2026-08-27 BEFORE this script was written. The 40-symbol universe, the
365/180 walk-forward, the 12-cell grid and both gates are fixed there.

ALL 12 CELLS ARE REPORTED regardless of outcome: +12 trials -> 141.
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

import polars as pl

from martex_quant.backtesting.carry import CarryConfig, build_symbol_frame, run_carry
from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.backtesting.pairs import PairsConfig, run_pairs
from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.stats.bootstrap import daily_mean_ci

ROOT = Path(".")
N_TRIALS = 141
SEED = 20260827
N_BOOT = 2_000
BLOCK = 30

Z_IN_GRID = (1.5, 2.0, 2.5)
Z_OUT_GRID = (0.0, 0.5)
HOLD_GRID = (30, 60)
PRIMARY = (2.0, 0.5, 30)

GATE_A_MIN_CAGR = 2.0
GATE_A_MIN_SHARPE = 1.0
GATE_A_DSR = 0.95
GATE_B_MAX_CORR = 0.30

CARRY_SYMBOLS = (
    "ADAUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "DOGEUSDT",
    "ETHUSDT",
    "LTCUSDT",
    "SOLUSDT",
    "XRPUSDT",
)


def load_panel() -> tuple[pl.DataFrame, list[str]]:
    store = ParquetStore(ROOT / "data/lake")
    symbols = json.loads((ROOT / "config/universe.json").read_text(encoding="utf-8"))["symbols"]
    frame: pl.DataFrame | None = None
    kept: list[str] = []
    for symbol in symbols:
        try:
            bars = store.read(symbol, Interval.D1)
        except FileNotFoundError:
            continue
        col = bars.sort("timestamp").select(
            pl.col("timestamp").cast(pl.Datetime("us", "UTC")).dt.truncate("1d"),
            pl.col("close").alias(symbol),
        )
        frame = col if frame is None else frame.join(col, on="timestamp", how="full", coalesce=True)
        kept.append(symbol)
    assert frame is not None
    return frame.sort("timestamp"), kept


def h63_carry_stream() -> pl.DataFrame:
    """Recompute the deployed carry spec here rather than trusting a cache."""
    store = ParquetStore(ROOT / "data/lake")
    frames = {}
    for symbol in CARRY_SYMBOLS:
        built = build_symbol_frame(
            store.read(symbol, Interval.D1),
            pl.read_parquet(ROOT / f"data/perp/{symbol}.parquet"),
            pl.read_parquet(ROOT / f"data/funding/{symbol}.parquet"),
        )
        frames[symbol] = built.with_columns(
            hold=(pl.col("funding").rolling_mean(30).shift(1) > 0.0).fill_null(value=False)
        )
    return run_carry(frames, CarryConfig()).daily.select(
        pl.col("timestamp").dt.truncate("1d"), pl.col("ret").alias("carry_ret")
    )


def corr_with(daily: pl.DataFrame, other: pl.DataFrame, column: str) -> tuple[float, int]:
    """Timestamp-joined correlation. Never positional (meta-finding 5)."""
    ours = daily.select(
        pl.col("timestamp").dt.truncate("1d").alias("timestamp"), pl.col("ret").alias("mine")
    )
    joined = ours.join(other, on="timestamp", how="inner").drop_nulls()
    if joined.height < 30:
        return float("nan"), joined.height
    return float(joined.select(pl.corr("mine", column)).item()), joined.height


def evaluate(daily: pl.DataFrame) -> dict[str, float]:
    rets = daily["ret"].to_list()
    equity = daily.select("timestamp", "equity", pl.lit(1.0).alias("exposure"))
    metrics = compute_metrics(equity, [], Interval.D1)
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
        "mean_open": float(daily["n_open"].mean() or 0.0),
        "mean_candidates": float(daily["n_candidates"].mean() or 0.0),
    }


def main() -> None:
    frame, symbols = load_panel()
    print("=" * 78)
    print("H64 — COINTEGRATED PAIRS, family F4 (12 cells, trials 130-141 -> 141)")
    print("=" * 78)
    print(f"\nUniverse: {len(symbols)} symbols with lake data")
    print(
        f"Panel: {frame.height} days, "
        f"{str(frame['timestamp'].min())[:10]} -> {str(frame['timestamp'].max())[:10]}"
    )
    print("Walk-forward: 365d formation -> 180d trading, hedge ratio frozen at formation\n")

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
    carry = h63_carry_stream()

    results: dict[tuple[float, float, int], dict[str, float]] = {}
    print("--- the declared 12-cell grid (ALL cells reported) ---")
    print(
        f"  {'z_in':>5} {'z_out':>6} {'hold':>5} | {'Sharpe':>7} {'CAGR':>8} {'MDD':>8} "
        f"{'DSR':>7} {'open':>5} {'cand':>6}"
    )
    for z_in, z_out, hold in product(Z_IN_GRID, Z_OUT_GRID, HOLD_GRID):
        config = PairsConfig(z_in=z_in, z_out=z_out, max_hold_days=hold)
        daily = run_pairs(frame, symbols, config)
        got = evaluate(daily)
        results[(z_in, z_out, hold)] = got
        star = " *" if (z_in, z_out, hold) == PRIMARY else "  "
        print(
            f"  {z_in:>5.1f} {z_out:>6.1f} {hold:>5}{star}| {got['sharpe']:>7.2f} "
            f"{got['cagr']:>+7.2f}% {got['mdd']:>7.2f}% {got['dsr']:>7.4f} "
            f"{got['mean_open']:>5.1f} {got['mean_candidates']:>6.1f}"
        )

    print("\n  (* = primary cell, nominated in the pre-registration)")

    config = PairsConfig(z_in=PRIMARY[0], z_out=PRIMARY[1], max_hold_days=int(PRIMARY[2]))
    primary_daily = run_pairs(frame, symbols, config)
    p = results[PRIMARY]
    corr_rot, n_rot = corr_with(primary_daily, rot_ret, "rot_ret")
    corr_carry, n_carry = corr_with(primary_daily, carry, "carry_ret")

    print("\n" + "-" * 78)
    print("GATES (primary cell z_in=2.0, z_out=0.5, hold=30)")
    print("-" * 78)
    a1 = p["ci_low"] > 0.0
    a2 = p["cagr"] >= GATE_A_MIN_CAGR
    a3 = p["sharpe"] >= GATE_A_MIN_SHARPE
    a4 = p["dsr"] >= GATE_A_DSR
    b5 = abs(corr_rot) < GATE_B_MAX_CORR
    b6 = abs(corr_carry) < GATE_B_MAX_CORR

    def mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    print(
        f"  A1 mean > 0, CI excludes zero : {p['ci_point'] * 1e4:+.3f}bp/day, "
        f"low {p['ci_low'] * 1e4:+.3f}bp  {mark(a1)}"
    )
    print(f"  A2 CAGR >= {GATE_A_MIN_CAGR:.0f}%/yr             : {p['cagr']:+.2f}%  {mark(a2)}")
    print(f"  A3 Sharpe >= {GATE_A_MIN_SHARPE:.1f}              : {p['sharpe']:.2f}  {mark(a3)}")
    print(f"  A4 DSR >= {GATE_A_DSR:.2f} @ {N_TRIALS}        : {p['dsr']:.4f}  {mark(a4)}")
    print(
        f"  B5 |corr| rotation-stop < {GATE_B_MAX_CORR:.2f}  : "
        f"{corr_rot:+.4f} (n={n_rot})  {mark(b5)}"
    )
    print(
        f"  B6 |corr| H63 carry < {GATE_B_MAX_CORR:.2f}      : "
        f"{corr_carry:+.4f} (n={n_carry})  {mark(b6)}"
    )

    gate_a = a1 and a2 and a3 and a4
    gate_b = b5 and b6
    print("\n" + "=" * 78)
    if gate_a and gate_b:
        print("VERDICT: GATE A + GATE B PASS -> third independent edge,")
        print("eligible for a paper account and the combined book.")
    elif gate_a:
        print("VERDICT: STANDALONE-VIABLE — real, but correlated with something")
        print("already deployed. Not deployed; does NOT count toward the")
        print("eight-edge target. Per docs/research/standalone-viable-amendment.md.")
    else:
        print("VERDICT: KILLED — Gate A failed. Second confirmation that crypto")
        print("does not mean-revert at retail-reachable cost (with H04).")
    print("=" * 78)

    out = ROOT / "data/tmp/h64_pairs"
    out.mkdir(parents=True, exist_ok=True)
    primary_daily.write_parquet(out / "pairs_stream.parquet")
    (out / "verdict.json").write_text(
        json.dumps(
            {
                "grid": {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in results.items()},
                "corr_rotation_stop": corr_rot,
                "corr_carry": corr_carry,
                "gate_a": gate_a,
                "gate_b": gate_b,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
