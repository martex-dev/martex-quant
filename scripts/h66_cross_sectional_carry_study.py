"""H66: cross-sectional carry (top-K funding), against its gates.

    .venv/Scripts/python scripts/h66_cross_sectional_carry_study.py

Pre-registered in docs/hypotheses/66-cross-sectional-carry.md, committed
2026-08-27 BEFORE this script was written. The universe, the K grid, the
fixed L=30, and all eight bars are fixed there.

ALL THREE CELLS ARE REPORTED regardless of outcome: +3 trials -> 147.

Both incumbents -- the 34-symbol harvest (H65 spec) and the 8-symbol
harvest (H63 spec) -- are recomputed HERE, in this run, on the SHARED
window. Never imported across windows (graveyard-audit 2.1).
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
N_TRIALS = 147
SEED = 20260827
N_BOOT = 2_000
BLOCK = 30

LOOKBACK = 30  # inherited from H63/H65 plateaus; NOT re-tuned here
K_GRID = (3, 5, 10)
PRIMARY_K = 5

GATE_A_MIN_CAGR = 2.0
GATE_A_MIN_SHARPE = 1.0
GATE_A_DSR = 0.95
GATE_C_MAX_CORR = 0.30
GATE_C_MDD_SLACK = 3.0

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
# Harvest books (H63/H65 specs): a gated-off symbol leaves its share in
# cash, which is what "capital not deployed sits in cash" means there.
WIDE = CarryConfig(require_all_symbols=False)
# Top-K book (H66 spec): "capital is split equally across the symbols
# actually HELD", so K names deploy the full book rather than K/34 of it.
# Without this a top-K rule is not comparable to a harvest rule -- it would
# be measured mostly on idle cash.
TOPK = CarryConfig(require_all_symbols=False, allocate_over="held")


def load_frames() -> dict[str, pl.DataFrame]:
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


def with_trailing(frames: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    """Attach each symbol's own trailing funding, known through t-1."""
    return {
        symbol: frame.with_columns(
            tf=pl.col("funding").rolling_mean(LOOKBACK).shift(1),
        )
        for symbol, frame in frames.items()
    }


def harvest_hold(frames: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    """H63/H65 rule: hold whenever this symbol's own trailing funding > 0."""
    return {
        symbol: frame.with_columns(hold=(pl.col("tf") > 0.0).fill_null(value=False))
        for symbol, frame in frames.items()
    }


def top_k_hold(frames: dict[str, pl.DataFrame], k: int) -> dict[str, pl.DataFrame]:
    """H66 rule: hold only the K richest by trailing funding, and only if
    that symbol's own trailing funding is positive.

    The rank is computed across symbols per day from a long frame, so it
    uses the same ``tf`` values the harvest rule uses -- no new quantity,
    only a cross-sectional comparison of an existing one.
    """
    long = pl.concat(
        [
            frame.select("day", pl.lit(symbol).alias("symbol"), "tf")
            for symbol, frame in frames.items()
        ]
    ).drop_nulls("tf")
    ranked = long.with_columns(
        rank=pl.col("tf").rank(method="ordinal", descending=True).over("day")
    ).with_columns(hold=(pl.col("rank") <= k) & (pl.col("tf") > 0.0))

    out: dict[str, pl.DataFrame] = {}
    for symbol, frame in frames.items():
        flags = ranked.filter(pl.col("symbol") == symbol).select("day", "hold")
        out[symbol] = frame.join(flags, on="day", how="left").with_columns(
            pl.col("hold").fill_null(value=False)
        )
    return out


def clip_to(daily: pl.DataFrame, lo: object, hi: object) -> pl.DataFrame:
    return daily.filter((pl.col("timestamp") >= lo) & (pl.col("timestamp") <= hi))


def evaluate(daily: pl.DataFrame) -> dict[str, float]:
    rets = daily["ret"].to_list()
    curve = daily.with_columns(eq=(1.0 + pl.col("ret")).cum_prod() * 10_000.0).select(
        "timestamp", pl.col("eq").alias("equity"), pl.lit(1.0).alias("exposure")
    )
    metrics = compute_metrics(curve, [], Interval.D1)
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
    tail = daily.tail(365)["ret"]
    return {
        "cagr": metrics.cagr_pct,
        "sharpe": metrics.sharpe,
        "mdd": metrics.max_drawdown_pct,
        "ci_low": ci.low,
        "ci_point": ci.point,
        "dsr": dsr,
        "held": float(daily["n_symbols"].mean() or 0.0),
        "last365": float(tail.sum() / (365 / 365.25) * 100.0),
    }


def main() -> None:
    frames = with_trailing(load_frames())
    wide_symbols = sorted(frames)
    inc8 = {s: f for s, f in frames.items() if s in INCUMBENT_8}

    print("=" * 78)
    print("H66 — CROSS-SECTIONAL CARRY, top-K funding (3 cells, 145-147 -> 147)")
    print("=" * 78)
    print(f"\nUniverse: {len(wide_symbols)} symbols. L={LOOKBACK} inherited, not re-tuned.\n")

    run_h65 = run_carry(harvest_hold(frames), WIDE)
    run_h63 = run_carry(harvest_hold(inc8), WIDE)
    runs_k = {k: run_carry(top_k_hold(frames, k), TOPK) for k in K_GRID}

    lo = max(
        run_h65.daily["timestamp"].min(),
        run_h63.daily["timestamp"].min(),
        *[r.daily["timestamp"].min() for r in runs_k.values()],
    )
    hi = min(
        run_h65.daily["timestamp"].max(),
        run_h63.daily["timestamp"].max(),
        *[r.daily["timestamp"].max() for r in runs_k.values()],
    )
    print(f"Shared window: {str(lo)[:10]} -> {str(hi)[:10]}\n")

    h65 = evaluate(clip_to(run_h65.daily, lo, hi))
    h63 = evaluate(clip_to(run_h63.daily, lo, hi))
    print("Incumbents, recomputed in THIS run on THIS window:")
    print(
        f"  harvest-all, 34 sym (H65): Sharpe {h65['sharpe']:5.2f}  CAGR {h65['cagr']:+6.2f}%  "
        f"MDD {h65['mdd']:6.2f}%  held~{h65['held']:.1f}"
    )
    print(
        f"  harvest-all,  8 sym (H63): Sharpe {h63['sharpe']:5.2f}  CAGR {h63['cagr']:+6.2f}%  "
        f"MDD {h63['mdd']:6.2f}%  held~{h63['held']:.1f}"
    )

    results: dict[int, dict[str, float]] = {}
    print("\n--- the declared K grid (ALL cells reported) ---")
    for k in K_GRID:
        got = evaluate(clip_to(runs_k[k].daily, lo, hi))
        results[k] = got
        star = " (PRIMARY)" if k == PRIMARY_K else ""
        print(f"\n  K={k}{star}")
        print(
            f"    Sharpe {got['sharpe']:6.2f}  CAGR {got['cagr']:+7.2f}%  "
            f"MDD {got['mdd']:6.2f}%  DSR {got['dsr']:.4f}"
        )
        print(
            f"    mean {got['ci_point'] * 1e4:+.3f}bp/day  CI low "
            f"{got['ci_low'] * 1e4:+.3f}bp  last365 {got['last365']:+.2f}%/yr"
        )

    p = results[PRIMARY_K]
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
        clip_to(runs_k[PRIMARY_K].daily, lo, hi)
        .select(pl.col("timestamp").dt.truncate("1d"), pl.col("ret").alias("mine"))
        .join(rot_ret, on="timestamp", how="inner")
        .drop_nulls()
    )
    corr = (
        float(joined.select(pl.corr("mine", "rot_ret")).item())
        if joined.height >= 30
        else float("nan")
    )

    print("\n" + "-" * 78)
    print(f"GATES (primary cell K={PRIMARY_K})")
    print("-" * 78)
    a1 = p["ci_low"] > 0.0
    a2 = p["cagr"] >= GATE_A_MIN_CAGR
    a3 = p["sharpe"] >= GATE_A_MIN_SHARPE
    a4 = p["dsr"] >= GATE_A_DSR
    b5 = p["sharpe"] > h65["sharpe"]
    b6 = p["sharpe"] > h63["sharpe"]
    c7 = abs(corr) < GATE_C_MAX_CORR
    c8 = p["mdd"] >= h65["mdd"] - GATE_C_MDD_SLACK

    def mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    print(f"  A1 CI excludes zero          : {p['ci_low'] * 1e4:+.3f}bp  {mark(a1)}")
    print(f"  A2 CAGR >= {GATE_A_MIN_CAGR:.0f}%/yr            : {p['cagr']:+.2f}%  {mark(a2)}")
    print(f"  A3 Sharpe >= {GATE_A_MIN_SHARPE:.1f}             : {p['sharpe']:.2f}  {mark(a3)}")
    print(f"  A4 DSR >= {GATE_A_DSR:.2f} @ {N_TRIALS}       : {p['dsr']:.4f}  {mark(a4)}")
    print(
        f"  B5 Sharpe > harvest-34 {h65['sharpe']:.2f}  : {p['sharpe']:.2f}  {mark(b5)}"
        "   <- SELECT vs HARVEST"
    )
    print(f"  B6 Sharpe > harvest-8  {h63['sharpe']:.2f}  : {p['sharpe']:.2f}  {mark(b6)}")
    print(f"  C7 |corr| rot-stop < {GATE_C_MAX_CORR:.2f}     : {corr:+.4f}  {mark(c7)}")
    print(
        f"  C8 MDD within {GATE_C_MDD_SLACK:.0f}pt of {h65['mdd']:.2f}% : "
        f"{p['mdd']:.2f}%  {mark(c8)}"
    )

    gate_a, gate_b, gate_c = a1 and a2 and a3 and a4, b5 and b6, c7 and c8
    print("\n" + "=" * 78)
    if gate_a and gate_b and gate_c:
        print("VERDICT: A + B + C PASS -> selection beats harvesting; H65's")
        print("select/harvest refinement is CONFIRMED. Replaces H63 as carry spec.")
    elif gate_a and gate_c and not b5:
        print("VERDICT: STANDALONE-VIABLE — and H65's refinement is WRONG.")
        print("Selection does NOT beat harvesting for carry, so select-vs-harvest")
        print("does not explain why breadth hurt. Recorded as a live edge on the")
        print("bench, not deployed. Per standalone-viable-amendment.md.")
    elif gate_a and gate_b and not c8:
        print("VERDICT: STANDALONE-VIABLE — return improved, RISK GOT WORSE.")
        print("The §3 squeeze story is the likely mechanism. Not deployed without")
        print("a re-registered risk study.")
    elif gate_a:
        print("VERDICT: STANDALONE-VIABLE — real edge, fails its comparison bars.")
    else:
        print("VERDICT: KILLED — Gate A failed.")
    print("=" * 78)

    out = ROOT / "data/tmp/h66_carry"
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(
        json.dumps(
            {
                "harvest_34": h65,
                "harvest_8": h63,
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
