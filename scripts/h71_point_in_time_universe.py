"""H71: does the deployed spec survive a universe chosen without hindsight?

    .venv/Scripts/python scripts/h71_point_in_time_universe.py

Pre-registered in docs/hypotheses/71-point-in-time-universe.md, committed
2026-08-28 BEFORE this script was written (commit db3e27a). The pool, the
selection rule, the strategy, the walk-forward protocol, the cells and
all four bars are fixed by that document. The STRATEGY is not varied at
all -- only which symbols it may rank.

Trials 171-172 (reselection cadence 90d and 365d).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from martex_quant.backtesting.metrics import (
    Metrics,
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from martex_quant.backtesting.walkforward import walk_forward_windows
from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.features.universe import UniverseSchedule, point_in_time_universes
from martex_quant.stats.bootstrap import CI, daily_mean_ci
from martex_quant.strategies.masked import UniverseMasked
from martex_quant.strategies.stops import StopVolTargetRotation

ROOT = Path(".")
POOL = ROOT / "data/pool"

# ---------------------------------------------------------------- FIXED BY
# THE PRE-REGISTRATION (docs/hypotheses/71-point-in-time-universe.md).
# Do not edit any constant below to chase a result.
UNIVERSE_SIZE = 40
VOLUME_WINDOW = 30
MIN_HISTORY = 90
CELLS = (90, 365)  # reselection cadence, days
PRIMARY_CELL = 90

TRAIN, TEST = 365, 90
ROT_GRID = (30, 90)
TOP_K = 2
TARGET_VOL, VOL_WINDOW = 0.30, 30
CONFIG = MultiBacktestConfig(initial_cash=10_000.0)

WINDOW_END = datetime(2026, 7, 9, tzinfo=UTC)  # the frozen research window
N_TRIALS = 172
SEED = 20260828
N_BOOT = 2_000
BLOCK_DAYS = 30

BAR_MIN_SHARPE = 1.0
BAR_DSR = 0.95
BAR_SHARPE_FRACTION = 0.70  # Gate B, a declared judgment call
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Book:
    label: str
    equity: pl.DataFrame
    returns: pl.DataFrame


def load_pool() -> dict[str, pl.DataFrame]:
    frames: dict[str, pl.DataFrame] = {}
    for path in sorted(POOL.glob("*.parquet")):
        frame = pl.read_parquet(path).filter(pl.col("timestamp") <= WINDOW_END)
        if frame.height > MIN_HISTORY:
            frames[path.stem] = frame
    return frames


def load_incumbent_frames(
    pool: dict[str, pl.DataFrame],
) -> tuple[dict[str, pl.DataFrame], list[str]]:
    """The hindsight 40, from the pool where possible.

    Section 7: both arms should share one data source. A universe symbol
    absent from the pool has been DELISTED since the 2026-07-12 snapshot,
    which is itself the survivorship story; it falls back to the frozen
    lake so the incumbent stays faithful, and it is reported.
    """
    symbols: list[str] = json.loads((ROOT / "config/universe.json").read_text("utf-8"))["symbols"]
    store = ParquetStore(ROOT / "data/lake")
    frames: dict[str, pl.DataFrame] = {}
    fell_back: list[str] = []
    for symbol in symbols:
        if symbol in pool:
            frames[symbol] = pool[symbol]
            continue
        try:
            frames[symbol] = store.read(symbol, Interval.D1).filter(
                pl.col("timestamp") <= WINDOW_END
            )
            fell_back.append(symbol)
        except Exception:
            continue
    return frames, fell_back


# The engine unpacks bars positionally (Bar(*row)), so it must be handed
# exactly the OHLCV columns. Pool frames carry quote_volume as well --
# that column is for the SELECTOR, never for the engine.
OHLCV = ("timestamp", "open", "high", "low", "close", "volume")


def slice_frames(
    frames: dict[str, pl.DataFrame], start: datetime, end: datetime, keep: set[str] | None = None
) -> dict[str, pl.DataFrame]:
    out: dict[str, pl.DataFrame] = {}
    for symbol, df in frames.items():
        if keep is not None and symbol not in keep:
            continue
        part = df.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))
        if part.height > 30:
            out[symbol] = part.select(OHLCV)
    return out


def wf_stream(
    frames: dict[str, pl.DataFrame],
    master: list[datetime],
    schedule: UniverseSchedule | None,
) -> pl.DataFrame:
    """The champion walk-forward, with an optional point-in-time mask.

    When a schedule is given, only the symbols it ever selects inside a
    window are handed to the engine. That is purely a speed measure and
    changes nothing: a symbol the mask never admits cannot be held.
    """

    def build(lookback: int) -> StopVolTargetRotation | UniverseMasked:
        base = StopVolTargetRotation(lookback, TOP_K, TARGET_VOL, VOL_WINDOW)
        return base if schedule is None else UniverseMasked(base, schedule)

    stitched: list[pl.DataFrame] = []
    level = 10_000.0
    for window in walk_forward_windows(len(master), TRAIN, TEST):
        t0 = master[window.train_start]
        t1 = master[window.train_end - 1] + timedelta(days=1)
        t2 = master[window.test_end - 1] + timedelta(days=1)

        keep: set[str] | None = None
        if schedule is not None:
            keep = set()
            for when, symbols in schedule.entries:
                if t0.date() - timedelta(days=400) <= when <= t2.date():
                    keep |= set(symbols)

        best_param, best_sharpe = ROT_GRID[0], float("-inf")
        for lookback in ROT_GRID:
            train = run_multi_backtest(
                slice_frames(frames, t0, t1, keep),
                build(lookback),
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
            slice_frames(frames, warm, t2, keep),
            build(best_param),
            config=CONFIG,
            warmup_bars=max(best_param, VOL_WINDOW) + 1,
        )
        curve = test.equity_curve.filter(pl.col("timestamp") >= t1)
        if curve.height == 0:
            continue
        first, last = curve["equity"][0], curve["equity"][-1]
        stitched.append(curve.with_columns(pl.col("equity") * (level / first)))
        level *= last / first
    return pl.concat(stitched)


def to_book(label: str, equity: pl.DataFrame) -> Book:
    returns = equity.select("timestamp", pl.col("equity").pct_change().fill_null(0.0).alias("ret"))
    return Book(label=label, equity=equity, returns=returns)


def restate(series: pl.Series, variance: float) -> tuple[Metrics, CI, float]:
    equity = pl.DataFrame({"ret": series}).select(
        (1.0 + pl.col("ret")).cum_prod().alias("equity"),
        pl.lit(1.0).alias("exposure"),
    )
    metrics = compute_metrics(equity, [], Interval.D1)
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
    dsr = probabilistic_sharpe_ratio(
        pp,
        n_obs=series.len(),
        skew=float(skew) if skew is not None else 0.0,
        kurtosis=(float(kurt) + 3.0) if kurt is not None else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, variance),
    )
    return metrics, ci, dsr


def main() -> None:
    print("=" * 104)
    print("H71 - POINT-IN-TIME UNIVERSE: is the rotation edge hindsight? (trials 171-172)")
    print("=" * 104)

    pool = load_pool()
    incumbent_frames, fell_back = load_incumbent_frames(pool)
    master = pool["BTCUSDT"]["timestamp"].to_list()
    print(
        f"\nPool: {len(pool)} symbols, window ends {str(WINDOW_END)[:10]}. "
        f"Hindsight universe: {len(incumbent_frames)} symbols."
    )
    if fell_back:
        print(
            f"  DELISTED since the 2026-07-12 snapshot (fell back to the frozen lake): "
            f"{', '.join(fell_back)}"
        )

    start = master[0] + timedelta(days=MIN_HISTORY)
    schedules = {
        cadence: point_in_time_universes(
            pool,
            size=UNIVERSE_SIZE,
            volume_window=VOLUME_WINDOW,
            min_history=MIN_HISTORY,
            reselect_every=cadence,
            start=start,
            end=WINDOW_END,
        )
        for cadence in CELLS
    }

    hindsight = set(incumbent_frames)
    print("\n--- Section 5.2 diagnostic: how much of the hindsight 40 was actually top-40? ---")
    print(f"    {'date':12}{'rankable':>10}{'overlap with the hindsight 40':>32}")
    primary = schedules[PRIMARY_CELL]
    shown = [e for i, e in enumerate(primary.entries) if i % 4 == 0]
    for when, symbols in shown:
        overlap = len(symbols & hindsight)
        print(f"    {str(when):12}{len(symbols):>10}{overlap:>20} / 40 ({overlap / 40:>5.0%})")

    print("\n--- running the books (this is the slow part) ---")
    incumbent = to_book("hindsight 40 (incumbent)", wf_stream(incumbent_frames, master, None))
    print("  incumbent done")
    books = {}
    for cadence in CELLS:
        books[cadence] = to_book(
            f"point-in-time, {cadence}d", wf_stream(pool, master, schedules[cadence])
        )
        print(f"  point-in-time {cadence}d done")

    common = incumbent.returns.rename({"ret": "ret_inc"})
    for cadence in CELLS:
        common = common.join(
            books[cadence].returns.rename({"ret": f"ret_{cadence}"}),
            on="timestamp",
            how="inner",
        )
    common = common.sort("timestamp")
    cols = ["ret_inc", *[f"ret_{c}" for c in CELLS]]
    pps = [(common[c].mean() or 0.0) / (common[c].std() or 1.0) for c in cols]
    variance = float(pl.Series(pps).var() or 0.0)

    stated = {c: restate(common[c], variance) for c in cols}

    print(
        f"\n--- the cells, identical window ({common.height} days, "
        f"{str(common['timestamp'].min())[:10]} -> {str(common['timestamp'].max())[:10]}) ---"
    )
    print(
        f"  {'book':30}{'CAGR':>10}{'Sharpe':>9}{'MDD':>10}"
        f"{'mean bp/day':>13}{'95% CI (bp)':>22}{'DSR':>8}"
    )
    labels = {"ret_inc": incumbent.label, **{f"ret_{c}": books[c].label for c in CELLS}}
    for col in cols:
        metrics, ci, dsr = stated[col]
        mark = "  <- PRIMARY" if col == f"ret_{PRIMARY_CELL}" else ""
        print(
            f"  {labels[col]:30}{metrics.cagr_pct:>9.2f}%{metrics.sharpe:>9.2f}"
            f"{metrics.max_drawdown_pct:>9.2f}%{ci.point * 1e4:>13.3f}"
            f"{'[' + f'{ci.low * 1e4:+.3f}, {ci.high * 1e4:+.3f}' + ']':>22}{dsr:>8.4f}{mark}"
        )

    inc_m, _, _ = stated["ret_inc"]
    pri_m, pri_ci, pri_dsr = stated[f"ret_{PRIMARY_CELL}"]

    print("\n--- the four pre-registered bars (Section 5) ---")

    def line(label: str, measured: str, ok: bool) -> None:
        print(f"  {label:<46} {measured:<32} -> {'PASS' if ok else 'FAIL'}")

    a1 = pri_m.sharpe >= BAR_MIN_SHARPE
    a2 = pri_ci.low > 0.0
    a3 = pri_dsr >= BAR_DSR
    b4 = pri_m.sharpe >= inc_m.sharpe * BAR_SHARPE_FRACTION
    line(f"A1. Sharpe >= {BAR_MIN_SHARPE:.1f}", f"{pri_m.sharpe:.2f}", a1)
    line(
        "A2. mean daily net > 0, CI excludes zero",
        f"{pri_ci.point * 1e4:+.3f}bp, low {pri_ci.low * 1e4:+.3f}bp",
        a2,
    )
    line(f"A3. DSR_global >= {BAR_DSR:.2f} @ {N_TRIALS}", f"{pri_dsr:.4f}", a3)
    line(
        f"B4. Sharpe >= {BAR_SHARPE_FRACTION:.0%} of hindsight's",
        f"{pri_m.sharpe:.2f} vs {inc_m.sharpe * BAR_SHARPE_FRACTION:.2f} needed",
        b4,
    )
    print(
        f"\n  Gate A {'PASS' if a1 and a2 and a3 else 'FAIL'}   Gate B {'PASS' if b4 else 'FAIL'}"
    )
    print(
        f"  Sharpe retained: {pri_m.sharpe / inc_m.sharpe:.0%} of the hindsight universe's "
        f"({pri_m.sharpe:.2f} vs {inc_m.sharpe:.2f})"
    )

    print("\n--- Section 5.1: were the predictions right? ---")
    early = [e for e in primary.entries if e[0].year in (2019, 2020)]
    if early:
        overlaps = [len(s & hindsight) / 40 for _, s in early]
        mean_overlap = sum(overlaps) / len(overlaps)
        print(
            f"  predicted 2019-2020 overlap < 40%: measured "
            f"{mean_overlap:.0%}  -> {'RIGHT' if mean_overlap < 0.40 else 'WRONG'}"
        )
    print(
        f"  predicted Sharpe falls to 0.7-1.2: measured {pri_m.sharpe:.2f}  -> "
        f"{'RIGHT' if 0.7 <= pri_m.sharpe <= 1.2 else 'WRONG'}"
    )

    print("\n--- reported, not gated: per-year ---")
    by_year = common.with_columns(year=pl.col("timestamp").dt.year())
    print(f"  {'year':6}{'n':>6}{'hindsight':>12}{'point-in-time':>15}{'gap':>10}")
    for year, group in sorted(by_year.group_by("year"), key=lambda kv: kv[0]):
        n = group.height
        inc = group["ret_inc"].sum() / (n / 365.25) * 100.0
        pit = group[f"ret_{PRIMARY_CELL}"].sum() / (n / 365.25) * 100.0
        print(f"  {year[0]:<6}{n:>6}{inc:>11.2f}%{pit:>14.2f}%{pit - inc:>9.2f}")

    turnover = primary.turnover
    if turnover:
        print(
            f"\n  universe turnover per {PRIMARY_CELL}d reselection: "
            f"mean {sum(turnover) / len(turnover):.1f} new names, max {max(turnover)}"
        )
    print("\n" + "=" * 104)


if __name__ == "__main__":
    main()
