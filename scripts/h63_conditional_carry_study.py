"""H63: funding-conditional carry, against its pre-registered gates.

    .venv/Scripts/python scripts/h63_conditional_carry_study.py

Pre-registered in docs/hypotheses/63-funding-conditional-carry.md, committed
2026-08-27 BEFORE this script was written. The 3-cell grid L in {7,30,90},
the always-on incumbent, and both gates are fixed by that document.

ALL THREE CELLS ARE REPORTED regardless of outcome: +3 trials -> 129.

The incumbent's figures are recomputed HERE, in this run, on the identical
window -- never imported from H62's write-up. That is the specific defect
recorded in docs/research/graveyard-audit.md 2.1, where FU-B1 was killed by
an absolute bar taken from a different window than the incumbent's own.
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
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.stats.bootstrap import daily_mean_ci

ROOT = Path(".")
N_TRIALS = 129
SEED = 20260827
N_BOOT = 2_000
BLOCK = 30

UNIVERSE = (
    "ADAUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "DOGEUSDT",
    "ETHUSDT",
    "LTCUSDT",
    "SOLUSDT",
    "XRPUSDT",
)
GRID_L = (7, 30, 90)
PRIMARY_L = 30

GATE_A_MIN_CAGR = 2.0
GATE_A_MIN_SHARPE = 1.0
GATE_A_DSR = 0.95


def load_frames() -> dict[str, pl.DataFrame]:
    store = ParquetStore(ROOT / "data/lake")
    frames: dict[str, pl.DataFrame] = {}
    for symbol in UNIVERSE:
        spot = store.read(symbol, Interval.D1)
        perp = pl.read_parquet(ROOT / f"data/perp/{symbol}.parquet")
        funding = pl.read_parquet(ROOT / f"data/funding/{symbol}.parquet")
        frames[symbol] = build_symbol_frame(spot, perp, funding)
    return frames


def with_filter(frames: dict[str, pl.DataFrame], lookback: int) -> dict[str, pl.DataFrame]:
    """Gate each symbol on its own trailing funding, known through t-1.

    ``shift(1)`` after the rolling mean is what keeps it strictly
    backward-looking: day t's decision may not see day t's funding.
    """
    return {
        symbol: frame.with_columns(
            hold=(pl.col("funding").rolling_mean(lookback).shift(1) > 0.0).fill_null(value=False)
        )
        for symbol, frame in frames.items()
    }


def evaluate(daily: pl.DataFrame, equity: pl.DataFrame, n_days: int) -> dict[str, float]:
    rets = daily["ret"].to_list()
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
    pp = (sum(rets) / len(rets)) / (series.std() or 1.0)
    skew, kurt = series.skew(), series.kurtosis()
    dsr = probabilistic_sharpe_ratio(
        pp,
        n_obs=len(rets),
        skew=float(skew) if skew is not None else 0.0,
        kurtosis=(float(kurt) + 3.0) if kurt is not None else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, float(series.var() or 0.0)),
    )
    year = daily.with_columns(y=pl.col("timestamp").dt.year()).filter(pl.col("y") == 2022)
    net_2022 = year["ret"].sum() / (year.height / 365.25) * 100.0 if year.height else float("nan")
    exposure = daily["exposure_share"].mean() if "exposure_share" in daily.columns else 1.0
    return {
        "cagr": metrics.cagr_pct,
        "sharpe": metrics.sharpe,
        "mdd": metrics.max_drawdown_pct,
        "ci_low": ci.low,
        "ci_point": ci.point,
        "ci_high": ci.high,
        "dsr": dsr,
        "net_2022": net_2022,
        "n_days": float(n_days),
        "exposure": float(exposure),
    }


def main() -> None:
    config = CarryConfig()
    base_frames = load_frames()

    # The incumbent, recomputed in THIS run on THIS window.
    base = run_carry(base_frames, config)
    inc = evaluate(base.daily, base.equity, base.n_days)

    print("=" * 78)
    print("H63 — FUNDING-CONDITIONAL CARRY (3 cells, trials 127-129 -> 129)")
    print("=" * 78)
    print(
        f"\nWindow: {base.n_days} days, "
        f"{str(base.daily['timestamp'].min())[:10]} -> "
        f"{str(base.daily['timestamp'].max())[:10]}"
    )
    print("\nIncumbent (H62 always-on), recomputed here on this same window:")
    print(
        f"  Sharpe {inc['sharpe']:.2f}   CAGR {inc['cagr']:+.2f}%   "
        f"MDD {inc['mdd']:.2f}%   2022 net {inc['net_2022']:+.2f}%/yr"
    )

    results: dict[int, dict[str, float]] = {}
    print("\n--- the declared 3-cell grid (ALL cells reported) ---")
    for lookback in GRID_L:
        run = run_carry(with_filter(base_frames, lookback), config)
        got = evaluate(run.daily, run.equity, run.n_days)
        results[lookback] = got
        star = " (PRIMARY)" if lookback == PRIMARY_L else ""
        print(f"\n  L={lookback}{star}")
        print(
            f"    Sharpe {got['sharpe']:6.2f}   CAGR {got['cagr']:+7.2f}%   "
            f"MDD {got['mdd']:6.2f}%   DSR {got['dsr']:.4f}"
        )
        print(
            f"    mean {got['ci_point'] * 1e4:+.3f}bp/day "
            f"CI [{got['ci_low'] * 1e4:+.3f}, {got['ci_high'] * 1e4:+.3f}]bp"
        )
        print(f"    2022 net {got['net_2022']:+.2f}%/yr")

    print("\n" + "-" * 78)
    print("GATES (primary cell L=30; the grid is reported, not selected from)")
    print("-" * 78)
    p = results[PRIMARY_L]
    a1 = p["ci_low"] > 0.0
    a2 = p["cagr"] >= GATE_A_MIN_CAGR
    a3 = p["sharpe"] >= GATE_A_MIN_SHARPE
    a4 = p["dsr"] >= GATE_A_DSR
    b5 = p["sharpe"] > inc["sharpe"]
    b6 = p["cagr"] > inc["cagr"]
    b7 = p["net_2022"] > inc["net_2022"]

    def mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    print(f"  A1 CI excludes zero          : {p['ci_low'] * 1e4:+.3f}bp  {mark(a1)}")
    print(f"  A2 CAGR >= {GATE_A_MIN_CAGR:.0f}%/yr            : {p['cagr']:+.2f}%  {mark(a2)}")
    print(f"  A3 Sharpe >= {GATE_A_MIN_SHARPE:.1f}             : {p['sharpe']:.2f}  {mark(a3)}")
    print(f"  A4 DSR >= {GATE_A_DSR:.2f} @ {N_TRIALS}       : {p['dsr']:.4f}  {mark(a4)}")
    print(f"  B5 Sharpe > incumbent {inc['sharpe']:.2f}   : {p['sharpe']:.2f}  {mark(b5)}")
    print(f"  B6 CAGR > incumbent {inc['cagr']:+.2f}%   : {p['cagr']:+.2f}%  {mark(b6)}")
    print(f"  B7 2022 > incumbent {inc['net_2022']:+.2f}%  : {p['net_2022']:+.2f}%  {mark(b7)}")

    # Robustness. Two things a Sharpe of this size must survive before it is
    # believed: is it an artifact of sitting in cash, and does it fix the
    # weakness it was built for? Neither can revise a bar; both can damn it.
    primary_frames = with_filter(base_frames, PRIMARY_L)
    total = sum(f.height for f in primary_frames.values())
    held = sum(int(f["hold"].sum()) for f in primary_frames.values())
    print("\n--- robustness ---")
    print(f"  deployment: {held / total:.1%} of symbol-days actually held")
    print("  (a high rate means the Sharpe is NOT an idle-capital artifact)")

    primary_run = run_carry(primary_frames, config)
    print("\n  year-by-year, incumbent -> L=30:")
    inc_year = base.daily.with_columns(y=pl.col("timestamp").dt.year())
    new_year = primary_run.daily.with_columns(y=pl.col("timestamp").dt.year())
    for (year, a), (_, b) in zip(
        sorted(inc_year.group_by("y"), key=lambda kv: kv[0]),
        sorted(new_year.group_by("y"), key=lambda kv: kv[0]),
        strict=True,
    ):
        an = a["ret"].sum() / (a.height / 365.25) * 100.0
        bn = b["ret"].sum() / (b.height / 365.25) * 100.0
        print(f"    {year[0]}  {an:+7.2f}%/yr -> {bn:+7.2f}%/yr")
    for window in (365, 730):
        an = base.daily.tail(window)["ret"].sum() / (window / 365.25) * 100.0
        bn = primary_run.daily.tail(window)["ret"].sum() / (window / 365.25) * 100.0
        print(f"    last {window:>3}d  {an:+7.2f}%/yr -> {bn:+7.2f}%/yr")

    gate_a = a1 and a2 and a3 and a4
    gate_b = b5 and b6 and b7
    print("\n" + "=" * 78)
    if gate_a and gate_b:
        print("VERDICT: GATE A + GATE B PASS -> candidate to replace H62 as the")
        print("carry spec; eligible for a paper account.")
    elif gate_a:
        print("VERDICT: STANDALONE-VIABLE — a real edge that does NOT beat")
        print("always-on carry. Not deployed; H62 remains the carry spec.")
        print("Per docs/research/standalone-viable-amendment.md.")
    else:
        print("VERDICT: KILLED — Gate A failed. This is the THIRD independent")
        print("confirmation of meta-finding 2: sizing beats switching.")
    print("=" * 78)

    out = ROOT / "data/tmp/h63_carry"
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(
        json.dumps(
            {
                "incumbent": inc,
                "grid": {str(k): v for k, v in results.items()},
                "gate_a": gate_a,
                "gate_b": gate_b,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
