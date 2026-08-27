"""H70: does the deployed rotation-stop spec hold too few slots?

    .venv/Scripts/python scripts/h70_rotation_concentration.py

Pre-registered in docs/hypotheses/70-rotation-concentration.md, committed
2026-08-28 BEFORE this script was written (commit 05d9b1f). The strategy,
the walk-forward protocol, the universe, the lookback grid, the cells and
all four bars are fixed by that document and are read from it, not chosen
here. K is the ONLY thing varied.

Trials 168-170 (K in {3, 5, 8}); K=2 is the deployed incumbent and is
recomputed in the same run rather than imported.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from martex_quant.backtesting.walkforward import walk_forward_windows
from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.stats.bootstrap import CI, daily_mean_ci
from martex_quant.strategies.stops import StopVolTargetRotation

ROOT = Path(".")

# ---------------------------------------------------------------- FIXED BY
# THE PRE-REGISTRATION (docs/hypotheses/70-rotation-concentration.md).
# Every value below is the DEPLOYED spec's. Do not edit to chase a result.
TRAIN, TEST = 365, 90
ROT_GRID = (30, 90)
TARGET_VOL, VOL_WINDOW = 0.30, 30
CONFIG = MultiBacktestConfig(initial_cash=10_000.0)

INCUMBENT_K = 2
CELLS = (3, 5, 8)
PRIMARY_K = 5
N_TRIALS = 170
SEED = 20260828
N_BOOT = 2_000
BLOCK_DAYS = 30

BAR_DSR = 0.95
BAR_CAGR_FRACTION = 0.75  # Section 5 Gate C, a declared judgment call

LIVE_START = datetime(2026, 7, 10, tzinfo=UTC)
LIVE_LOOKBACK = 90  # what the paper account reports in every mark
LIVE_WARMUP_DAYS = 200
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Book:
    k: int
    equity: pl.DataFrame
    returns: pl.DataFrame
    lookbacks: list[int]

    @property
    def label(self) -> str:
        return f"K={self.k}" + (" (incumbent)" if self.k == INCUMBENT_K else "")


def load_frames(lake: Path) -> dict[str, pl.DataFrame]:
    store = ParquetStore(lake)
    universe: list[str] = json.loads((ROOT / "config/universe.json").read_text(encoding="utf-8"))[
        "symbols"
    ]
    frames: dict[str, pl.DataFrame] = {}
    for symbol in universe:
        try:
            frames[symbol] = store.read(symbol, Interval.D1)
        except Exception:
            continue
    return frames


def slice_frames(
    frames: dict[str, pl.DataFrame], start: datetime, end: datetime
) -> dict[str, pl.DataFrame]:
    out: dict[str, pl.DataFrame] = {}
    for symbol, df in frames.items():
        part = df.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))
        if part.height > 30:
            out[symbol] = part
    return out


def rotation_wf_stream(frames: dict[str, pl.DataFrame], k: int) -> tuple[pl.DataFrame, list[int]]:
    """The champion walk-forward protocol, verbatim, with top_k = k.

    Copied in shape from scripts/h41_h42_fub1_studies.py so the incumbent
    this run recomputes is the same construction that produced the
    deployed spec's published figures -- and so any difference between
    cells is K and the L path it selects, nothing else.
    """
    master = frames["BTCUSDT"]["timestamp"].to_list()
    stitched: list[pl.DataFrame] = []
    chosen: list[int] = []
    level = 10_000.0
    for window in walk_forward_windows(len(master), TRAIN, TEST):
        t0 = master[window.train_start]
        t1 = master[window.train_end - 1] + timedelta(days=1)
        t2 = master[window.test_end - 1] + timedelta(days=1)

        best_param, best_sharpe = ROT_GRID[0], float("-inf")
        for lookback in ROT_GRID:
            train = run_multi_backtest(
                slice_frames(frames, t0, t1),
                StopVolTargetRotation(lookback, k, TARGET_VOL, VOL_WINDOW),
                config=CONFIG,
                warmup_bars=max(lookback, VOL_WINDOW) + 1,
            )
            if train.equity_curve.height < 30:
                continue
            sharpe = compute_metrics(train.equity_curve, [], Interval.D1).sharpe
            if sharpe > best_sharpe:
                best_param, best_sharpe = lookback, sharpe

        warm = t1 - timedelta(days=max(best_param, VOL_WINDOW) + 11)
        test = run_multi_backtest(
            slice_frames(frames, warm, t2),
            StopVolTargetRotation(best_param, k, TARGET_VOL, VOL_WINDOW),
            config=CONFIG,
            warmup_bars=max(best_param, VOL_WINDOW) + 1,
        )
        curve = test.equity_curve.filter(pl.col("timestamp") >= t1)
        if curve.height == 0:
            continue
        chosen.append(best_param)
        first, last = curve["equity"][0], curve["equity"][-1]
        stitched.append(curve.with_columns(pl.col("equity") * (level / first)))
        level *= last / first
    return pl.concat(stitched), chosen


def build(frames: dict[str, pl.DataFrame], k: int) -> Book:
    equity, lookbacks = rotation_wf_stream(frames, k)
    returns = equity.select("timestamp", pl.col("equity").pct_change().fill_null(0.0).alias("ret"))
    return Book(k=k, equity=equity, returns=returns, lookbacks=lookbacks)


def restate(book: Book, common: pl.DataFrame) -> tuple[object, CI, float]:
    """Metrics for one book on the COMMON window shared by every cell."""
    rets = common.select("timestamp", pl.col(f"ret_{book.k}").alias("ret"))
    equity = rets.select(
        "timestamp",
        (1.0 + pl.col("ret")).cum_prod().alias("equity"),
        pl.lit(1.0).alias("exposure"),
    )
    metrics = compute_metrics(equity, [], Interval.D1)
    series = rets["ret"]
    ci = daily_mean_ci(
        series.to_list(),
        block=BLOCK_DAYS,
        seed=SEED,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    pp = (series.mean() or 0.0) / (series.std() or 1.0)
    skew, kurt = series.skew(), series.kurtosis()
    # Variance over the cells' per-period Sharpes, the same estimator shape
    # the deployed spec's own DSR used (variance across the compared books).
    pps = [
        (common[f"ret_{c}"].mean() or 0.0) / (common[f"ret_{c}"].std() or 1.0)
        for c in (INCUMBENT_K, *CELLS)
    ]
    variance = float(pl.Series(pps).var() or 0.0)
    dsr = probabilistic_sharpe_ratio(
        pp,
        n_obs=series.len(),
        skew=float(skew) if skew is not None else 0.0,
        kurtosis=(float(kurt) + 3.0) if kurt is not None else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, variance),
    )
    return metrics, ci, dsr


def _rising(values: list[float]) -> bool:
    """Monotone non-decreasing. Section 5.1 predicted monotonicity in K."""
    return all(b >= a for a, b in zip(values, values[1:], strict=False))


def main() -> None:
    print("=" * 104)
    print("H70 - ROTATION CONCENTRATION: was K=2 ever the right number? (trials 168-170)")
    print("=" * 104)

    frames = load_frames(ROOT / "data/lake")
    print(
        f"\nFrozen lake: {len(frames)} symbols, "
        f"{str(frames['BTCUSDT']['timestamp'].min())[:10]} -> "
        f"{str(frames['BTCUSDT']['timestamp'].max())[:10]}"
    )
    print("Spec: StopVolTargetRotation(L, top_k=K, target 30%, window 30), champion")
    print(f"      walk-forward, L re-selected each {TEST}d from {list(ROT_GRID)}. K is the")
    print("      ONLY thing varied.\n")

    books = {k: build(frames, k) for k in (INCUMBENT_K, *CELLS)}

    common = books[INCUMBENT_K].returns.rename({"ret": f"ret_{INCUMBENT_K}"})
    for k in CELLS:
        common = common.join(
            books[k].returns.rename({"ret": f"ret_{k}"}), on="timestamp", how="inner"
        )
    common = common.sort("timestamp")
    print(
        f"Common window: {common.height} days, "
        f"{str(common['timestamp'].min())[:10]} -> {str(common['timestamp'].max())[:10]}"
    )

    stated = {k: restate(books[k], common) for k in (INCUMBENT_K, *CELLS)}

    print("\n--- the declared cells, all on the identical window, one run ---")
    print(
        f"  {'book':18}{'CAGR':>10}{'Sharpe':>9}{'MDD':>10}"
        f"{'mean bp/day':>13}{'95% CI (bp)':>22}{'DSR':>8}  L path"
    )
    for k in (INCUMBENT_K, *CELLS):
        metrics, ci, dsr = stated[k]
        counts = {lb: books[k].lookbacks.count(lb) for lb in ROT_GRID}
        path = " ".join(f"{lb}:{n}" for lb, n in counts.items())
        mark = "  <- PRIMARY" if k == PRIMARY_K else ""
        print(
            f"  {books[k].label:18}{metrics.cagr_pct:>9.2f}%{metrics.sharpe:>9.2f}"
            f"{metrics.max_drawdown_pct:>9.2f}%{ci.point * 1e4:>13.3f}"
            f"{'[' + f'{ci.low * 1e4:+.3f}, {ci.high * 1e4:+.3f}' + ']':>22}"
            f"{dsr:>8.4f}  {path}{mark}"
        )

    inc_metrics, _inc_ci, _inc_dsr = stated[INCUMBENT_K]
    pri_metrics, _pri_ci, pri_dsr = stated[PRIMARY_K]

    print(f"\n--- the four pre-registered bars (Section 5), judged on K={PRIMARY_K} ---")
    a1 = pri_metrics.sharpe > inc_metrics.sharpe
    a2 = pri_metrics.max_drawdown_pct > inc_metrics.max_drawdown_pct  # less negative
    b3 = pri_dsr >= BAR_DSR
    c4 = pri_metrics.cagr_pct >= inc_metrics.cagr_pct * BAR_CAGR_FRACTION

    def line(label: str, measured: str, ok: bool) -> None:
        print(f"  {label:<46} {measured:<32} -> {'PASS' if ok else 'FAIL'}")

    line(
        "A1. Sharpe > incumbent's",
        f"{pri_metrics.sharpe:.2f} vs {inc_metrics.sharpe:.2f}",
        a1,
    )
    line(
        "A2. MDD less severe than incumbent's",
        f"{pri_metrics.max_drawdown_pct:.2f}% vs {inc_metrics.max_drawdown_pct:.2f}%",
        a2,
    )
    line(f"B3. DSR_global >= {BAR_DSR:.2f} @ {N_TRIALS}", f"{pri_dsr:.4f}", b3)
    line(
        f"C4. CAGR >= {BAR_CAGR_FRACTION:.0%} of incumbent's",
        f"{pri_metrics.cagr_pct:+.2f}% vs {inc_metrics.cagr_pct * BAR_CAGR_FRACTION:+.2f}% needed",
        c4,
    )
    print(
        f"\n  Gate A {'PASS' if a1 and a2 else 'FAIL'}   "
        f"Gate B {'PASS' if b3 else 'FAIL'}   "
        f"Gate C {'PASS' if c4 else 'FAIL'}"
    )

    print("\n--- Section 5.1: were the predictions right? (monotone in K?) ---")
    sharpes = [stated[k][0].sharpe for k in (INCUMBENT_K, *CELLS)]
    cagrs = [stated[k][0].cagr_pct for k in (INCUMBENT_K, *CELLS)]
    mdds = [stated[k][0].max_drawdown_pct for k in (INCUMBENT_K, *CELLS)]
    ks = (INCUMBENT_K, *CELLS)
    print(f"  K          {'  '.join(f'{k:>8}' for k in ks)}")
    print(f"  Sharpe     {'  '.join(f'{v:>8.2f}' for v in sharpes)}")
    print(f"  CAGR       {'  '.join(f'{v:>8.2f}' for v in cagrs)}")
    print(f"  MDD        {'  '.join(f'{v:>8.2f}' for v in mdds)}")
    print(
        f"  predicted: Sharpe rising {'YES' if _rising(sharpes) else 'NO'}; "
        f"CAGR falling {'YES' if _rising([-c for c in cagrs]) else 'NO'}; "
        f"MDD improving {'YES' if _rising(mdds) else 'NO'}"
    )

    print("\n--- Section 5.2 diagnostic: the LIVE paper window (NOT a bar, NOT a trial) ---")
    current = load_frames(ROOT / "data/lake-current")
    live_end = current["BTCUSDT"]["timestamp"].max()
    print(
        f"  data/lake-current, {str(LIVE_START)[:10]} -> {str(live_end)[:10]}, "
        f"run at L={LIVE_LOOKBACK}"
    )
    print(
        "  -- the lookback the live paper account actually reports in every mark.\n"
        "  The walk-forward protocol cannot serve this window: it needs complete\n"
        "  90-day test windows and has none covering it. 48 days is far too short\n"
        "  to conclude anything from."
    )
    warm = LIVE_START - timedelta(days=LIVE_WARMUP_DAYS)
    live_frames = slice_frames(current, warm, live_end + timedelta(days=1))
    print(f"  {'book':18}{'live return':>14}{'worst day':>12}{'MDD':>10}")
    for k in (INCUMBENT_K, *CELLS):
        result = run_multi_backtest(
            live_frames,
            StopVolTargetRotation(LIVE_LOOKBACK, k, TARGET_VOL, VOL_WINDOW),
            config=CONFIG,
            warmup_bars=max(LIVE_LOOKBACK, VOL_WINDOW) + 1,
        )
        live = result.equity_curve.filter(pl.col("timestamp") >= LIVE_START)
        if live.height < 2:
            print(f"  {books[k].label:18}{'n/a':>14}")
            continue
        rets = live.select(pl.col("equity").pct_change().drop_nulls().alias("ret"))["ret"]
        total = float(live["equity"][-1] / live["equity"][0] - 1.0)
        mdd = float((live["equity"] / live["equity"].cum_max() - 1.0).min()) * 100.0
        print(f"  {books[k].label:18}{total * 100:>13.2f}%{rets.min() * 100:>11.2f}%{mdd:>9.2f}%")
    print(
        "  Live paper accounts over the same period, for reference: "
        "rotation-stop -7.44%,\n  rotation -17.14%, vol-target (8 majors, all held) +5.84%."
    )

    print("\n--- reported, not gated: per-year (primary vs incumbent) ---")
    by_year = common.with_columns(year=pl.col("timestamp").dt.year())
    print(f"  {'year':6}{'n':>6}{'K=2':>11}{'K=' + str(PRIMARY_K):>11}")
    for year, group in sorted(by_year.group_by("year"), key=lambda kv: kv[0]):
        n = group.height
        inc = group[f"ret_{INCUMBENT_K}"].sum() / (n / 365.25) * 100.0
        pri = group[f"ret_{PRIMARY_K}"].sum() / (n / 365.25) * 100.0
        print(f"  {year[0]:<6}{n:>6}{inc:>10.2f}%{pri:>10.2f}%")

    print("\n" + "=" * 104)


if __name__ == "__main__":
    main()
