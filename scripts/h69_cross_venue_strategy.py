"""H69: cross-venue premium at strategy grade, against its six bars.

    .venv/Scripts/python scripts/h69_cross_venue_strategy.py

Pre-registered in docs/hypotheses/69-cross-venue-premium-strategy.md,
committed 2026-08-27 BEFORE this script was written (commit 34b11e5).
Every parameter is inherited verbatim from H68 -- universe, signal, the
90-day percentile window, the 90th-percentile threshold and the horizons.
Nothing here is searched. The only things this script adds are the two a
return stream cannot avoid having: capital allocation and fills.

Trials 165-167 (three holding periods).
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from martex_quant.backtesting.metrics import (
    Metrics,
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.features.crossvenue import build_signal_panel
from martex_quant.stats.bootstrap import CI, daily_mean_ci
from martex_quant.strategies.crossvenue import CrossVenuePremiumLadder, EqualWeightBuyAndHold

ROOT = Path(".")

# ---------------------------------------------------------------- FIXED BY
# THE PRE-REGISTRATION (docs/hypotheses/69-cross-venue-premium-strategy.md).
# All inherited from H68. Do not edit any constant below to chase a result.
PCT_WINDOW = 90
HIGH_PCT = 0.90
HORIZONS = (1, 7, 30)
VOLUME_FLOOR = 1_000_000.0
SIGNAL = "s2_adj_premium"
HOLDS = (1, 7, 30)
PRIMARY_HOLD = 7
BLOCK_DAYS = 30
N_BOOT = 2_000
SEED = 20260827
N_TRIALS = 167
INITIAL_CASH = 10_000.0
# Section 4.4 declares the window explicitly. The lake reaches back to
# 2017-08-17, but the venue signal does not exist before 2019-01-01, and
# letting the Gate B benchmark trade the 2017 bubble and the 2018 crash
# while the strategy sits in signal-less cash is not the comparison that
# was registered.
WINDOW_START = dt.datetime(2019, 1, 1, tzinfo=dt.UTC)

BAR_MIN_CAGR = 2.0
BAR_MIN_SHARPE = 1.0
BAR_MAX_CORR = 0.30
BAR_DSR = 0.95
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Book:
    label: str
    metrics: Metrics
    ci: CI
    dsr: float
    daily: pl.DataFrame  # timestamp, ret


def load_traded_frames(symbols: list[str]) -> dict[str, pl.DataFrame]:
    """The TRADED leg: the frozen research lake's Binance OHLCV.

    Section 4.4. The venue cache carries closes only and would give the
    engine no opens to fill at; more importantly this is the store every
    other strategy trial in the ledger executes against, and a fresh
    Binance pull was verified byte-identical to it on all 2,747
    overlapping closes (H68 Section 4.1).
    """
    store = ParquetStore(ROOT / "data/lake")
    return {
        s: store.read(f"{s}USDT", Interval.D1).filter(pl.col("timestamp") >= WINDOW_START)
        for s in symbols
    }


def qualifier_sets(panel: pl.DataFrame) -> dict[dt.date, tuple[str, ...]]:
    """{entry date -> symbols in the top decile of their own trailing window}.

    Ranks come from the panel H68 measured, so the strategy trades exactly
    the observations the info study scored. Every rank is a trailing
    quantity, so this table contains no look-ahead.
    """
    qualifying = panel.drop_nulls(f"pct_{SIGNAL}").filter(pl.col(f"pct_{SIGNAL}") >= HIGH_PCT)
    grouped = qualifying.group_by("day").agg(pl.col("symbol").sort())
    return {
        row["day"].date(): tuple(row["symbol"]) for row in grouped.sort("day").iter_rows(named=True)
    }


def to_book(label: str, equity_curve: pl.DataFrame) -> Book:
    metrics = compute_metrics(equity_curve, [], Interval.D1)
    daily = equity_curve.select(
        pl.col("timestamp"),
        pl.col("equity").pct_change().alias("ret"),
    ).drop_nulls("ret")
    rets = daily["ret"]
    ci = daily_mean_ci(
        rets.to_list(),
        block=BLOCK_DAYS,
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
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, float(rets.var() or 0.0)),
    )
    return Book(label=label, metrics=metrics, ci=ci, dsr=dsr, daily=daily)


def rotation_stop_returns() -> pl.DataFrame:
    series = SeriesStore(ROOT)
    return (
        series.read(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
        .sort("timestamp")
        .select(
            pl.col("timestamp").dt.truncate("1d").cast(pl.Datetime("us", "UTC")).alias("timestamp"),
            pl.col("equity").pct_change().fill_null(0.0).alias("rot_ret"),
        )
        .group_by("timestamp")
        .agg(pl.col("rot_ret").last())
    )


def correlation(book: Book, rot: pl.DataFrame) -> tuple[float, int, pl.DataFrame]:
    joined = (
        book.daily.select(
            pl.col("timestamp").dt.truncate("1d").cast(pl.Datetime("us", "UTC")).alias("timestamp"),
            pl.col("ret").alias("ours"),
        )
        .join(rot, on="timestamp", how="inner")
        .drop_nulls()
    )
    if joined.height < 30:
        return float("nan"), joined.height, joined
    return float(joined.select(pl.corr("ours", "rot_ret")).item()), joined.height, joined


def line(label: str, measured: str, ok: bool) -> None:
    print(f"  {label:<48} {measured:<30} -> {'PASS' if ok else 'FAIL'}")


def main() -> None:
    panel, kept, _rejected = build_signal_panel(
        ROOT, pct_window=PCT_WINDOW, horizons=HORIZONS, volume_floor=VOLUME_FLOOR
    )
    qualifiers = qualifier_sets(panel)
    frames = load_traded_frames(kept)

    print("=" * 100)
    print("H69 - CROSS-VENUE PREMIUM, STRATEGY GRADE (family F2, trials 165-167)")
    print("=" * 100)
    lake_end = max(f["timestamp"].max() for f in frames.values())
    lake_start = min(f["timestamp"].min() for f in frames.values())
    print(
        f"\nUniverse: {len(kept)} symbols (inherited from H68). "
        f"Traded leg: frozen lake, {str(lake_start)[:10]} -> {str(lake_end)[:10]}"
    )
    print(
        f"Signal: {SIGNAL} rank >= {HIGH_PCT:.2f} of trailing {PCT_WINDOW}d; "
        f"{len(qualifiers):,} entry days carry at least one qualifier"
    )
    print("Execution: decisions at the close, fills at the NEXT bar's open, 10bp fee + 1bp")
    print("           half-spread + 25bp participation impact, per side.\n")

    config = MultiBacktestConfig(initial_cash=INITIAL_CASH)
    books: dict[int, Book] = {}
    n_fills: dict[int, int] = {}
    for hold in HOLDS:
        result = run_multi_backtest(
            frames,
            CrossVenuePremiumLadder(qualifiers, hold=hold),
            config,
            warmup_bars=PCT_WINDOW,
        )
        books[hold] = to_book(f"hold={hold}d", result.equity_curve)
        n_fills[hold] = len(result.fills)

    benchmark_result = run_multi_backtest(
        frames, EqualWeightBuyAndHold(), config, warmup_bars=PCT_WINDOW
    )
    benchmark = to_book("equal-weight buy-and-hold", benchmark_result.equity_curve)

    print("--- the three declared cells, plus the Gate B benchmark (same run, same window) ---")
    print(
        f"  {'book':30}{'CAGR':>9}{'Sharpe':>8}{'MDD':>9}"
        f"{'mean bp/day':>13}{'95% CI (bp)':>22}{'DSR':>8}{'in mkt':>8}"
    )
    for hold in HOLDS:
        b = books[hold]
        mark = "  <- PRIMARY" if hold == PRIMARY_HOLD else ""
        print(
            f"  {b.label:30}{b.metrics.cagr_pct:>8.2f}%{b.metrics.sharpe:>8.2f}"
            f"{b.metrics.max_drawdown_pct:>8.2f}%{b.ci.point * 1e4:>13.3f}"
            f"{'[' + f'{b.ci.low * 1e4:+.3f}, {b.ci.high * 1e4:+.3f}' + ']':>22}"
            f"{b.dsr:>8.4f}{b.metrics.time_in_market_pct:>7.1f}%{mark}"
        )
    b = benchmark
    print(
        f"  {b.label:30}{b.metrics.cagr_pct:>8.2f}%{b.metrics.sharpe:>8.2f}"
        f"{b.metrics.max_drawdown_pct:>8.2f}%{b.ci.point * 1e4:>13.3f}"
        f"{'[' + f'{b.ci.low * 1e4:+.3f}, {b.ci.high * 1e4:+.3f}' + ']':>22}"
        f"{b.dsr:>8.4f}{b.metrics.time_in_market_pct:>7.1f}%  <- BENCHMARK"
    )

    primary = books[PRIMARY_HOLD]
    rot = rotation_stop_returns()
    corr, corr_n, joined = correlation(primary, rot)

    print("\n--- the six pre-registered bars (Section 5.1), judged on the primary ---")
    a1 = primary.ci.low > 0.0
    a2 = primary.metrics.cagr_pct >= BAR_MIN_CAGR
    a3 = primary.metrics.sharpe >= BAR_MIN_SHARPE
    a4 = primary.dsr >= BAR_DSR
    b5 = primary.metrics.sharpe > benchmark.metrics.sharpe
    c6 = abs(corr) < BAR_MAX_CORR

    line(
        "A1. mean daily net > 0, CI excludes zero",
        f"{primary.ci.point * 1e4:+.3f}bp, low {primary.ci.low * 1e4:+.3f}bp",
        a1,
    )
    line(f"A2. net CAGR >= {BAR_MIN_CAGR:.0f}%/yr", f"{primary.metrics.cagr_pct:+.2f}%", a2)
    line(f"A3. Sharpe >= {BAR_MIN_SHARPE:.1f}", f"{primary.metrics.sharpe:.2f}", a3)
    line(f"A4. DSR_global >= {BAR_DSR:.2f} @ {N_TRIALS}", f"{primary.dsr:.4f}", a4)
    line(
        "B5. Sharpe > buy-and-hold (same window)",
        f"{primary.metrics.sharpe:.2f} vs {benchmark.metrics.sharpe:.2f}",
        b5,
    )
    line(
        f"C6. |corr| with rotation-stop < {BAR_MAX_CORR:.2f}",
        f"{corr:+.4f} (n={corr_n})",
        c6,
    )

    gate_a = a1 and a2 and a3 and a4
    print(
        f"\n  Gate A {'PASS' if gate_a else 'FAIL'}   "
        f"Gate B {'PASS' if b5 else 'FAIL'}   "
        f"Gate C {'PASS' if c6 else 'FAIL'}"
    )

    # Section 6: the correlated branch was decided in advance. If this is
    # not an independent edge it must beat the DEPLOYED book head to head
    # on both Sharpe and CAGR to be a deployment candidate.
    if gate_a and not c6:
        print("\n--- Section 6 correlated branch: head-to-head vs the deployed book ---")
        rot_window = joined.select(pl.col("timestamp"), pl.col("rot_ret").alias("ret")).drop_nulls()
        rot_equity = rot_window.select(
            pl.col("timestamp"),
            (1.0 + pl.col("ret")).cum_prod().alias("equity"),
            pl.lit(1.0).alias("exposure"),
        )
        rot_metrics = compute_metrics(rot_equity, [], Interval.D1)
        ours = joined.select(
            pl.col("timestamp"),
            (1.0 + pl.col("ours")).cum_prod().alias("equity"),
            pl.lit(1.0).alias("exposure"),
        )
        our_metrics = compute_metrics(ours, [], Interval.D1)
        print(
            f"  on the shared {joined.height}-day window: "
            f"ours Sharpe {our_metrics.sharpe:.2f} / CAGR {our_metrics.cagr_pct:+.2f}%   "
            f"vs rotation-stop Sharpe {rot_metrics.sharpe:.2f} / "
            f"CAGR {rot_metrics.cagr_pct:+.2f}%"
        )
        beats = (
            our_metrics.sharpe > rot_metrics.sharpe and our_metrics.cagr_pct > rot_metrics.cagr_pct
        )
        print(f"  beats the incumbent on BOTH: {'yes' if beats else 'NO'}")

    print("\n--- Section 5.3 reported, not gated ---")
    m = primary.metrics
    print(
        f"  time in market {m.time_in_market_pct:.1f}%   MDD {m.max_drawdown_pct:.2f}%   "
        f"fills {n_fills[PRIMARY_HOLD]:,} (benchmark {len(benchmark_result.fills):,})"
    )
    rets = primary.daily["ret"]
    print(
        f"  skew {rets.skew():+.3f}   excess kurtosis {rets.kurtosis():+.2f}   "
        f"worst day {rets.min() * 100:+.2f}%   best day {rets.max() * 100:+.2f}%"
    )

    if corr_n >= 100:
        print("\n  tail-conditional check (H67 Section 8.4's PROPOSED bar, reported only):")
        for q, label in ((0.10, "worst decile"), (0.05, "worst 5%"), (0.01, "worst 1%")):
            thr = joined["rot_ret"].quantile(q)
            sub = joined.filter(pl.col("rot_ret") <= thr)
            print(
                f"    rotation-stop {label:<14} n={sub.height:>4}  "
                f"mean H69 return {(sub['ours'].mean() or 0.0) * 100:+.3f}%  "
                f"(unconditional {(joined['ours'].mean() or 0.0) * 100:+.3f}%)"
            )

    print("\n--- per-year (primary cell vs benchmark) ---")
    per_year = (
        primary.daily.with_columns(year=pl.col("timestamp").dt.year())
        .group_by("year")
        .agg(n=pl.len(), ours=pl.col("ret").sum(), vol=pl.col("ret").std())
        .sort("year")
    )
    bench_year = (
        benchmark.daily.with_columns(year=pl.col("timestamp").dt.year())
        .group_by("year")
        .agg(bench=pl.col("ret").sum())
        .sort("year")
    )
    merged = per_year.join(bench_year, on="year", how="left")
    for row in merged.iter_rows(named=True):
        ann = row["ours"] / (row["n"] / 365.25) * 100.0
        bench_ann = (row["bench"] or 0.0) / (row["n"] / 365.25) * 100.0
        sharpe = (row["ours"] / row["n"]) / (row["vol"] or 1.0) * math.sqrt(365.25)
        print(
            f"  {row['year']}  n={row['n']:>4}  ours {ann:+8.2f}%/yr  "
            f"Sharpe {sharpe:>6.2f}   buy-and-hold {bench_ann:+8.2f}%/yr"
        )

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
