"""Wide-universe rotation re-test (docs/research/wide-universe.md).

    .venv/Scripts/python scripts/wide_rotation_study.py

Same sized-rotation spec as hyp 11, on the ~40-coin universe, K in
{2, 5}. Bars pre-registered: Sharpe >= 85% of the 8-coin version's 0.90
on the same protocol, prop pass >= 45%, for at least one K.
"""

from __future__ import annotations

import json
import statistics
from datetime import timedelta
from pathlib import Path

import polars as pl

from trading_bot.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from trading_bot.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from trading_bot.backtesting.walkforward import walk_forward_windows
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.risk_management.prop_sim import PropFirmRules, simulate_evaluation
from trading_bot.strategies.rotation import VolTargetRotation

TRAIN, TEST = 365, 90
GRID = [30, 90]
N_TRIALS = 65
BASELINE_8COIN_SHARPE = 0.90  # hyp 11 sized variant, same protocol
FIRM_RULES = PropFirmRules(
    "1step-5k-static", 5_000.0, 0.10, None, 0.03, None, 51.80, static_max_loss_pct=0.06
)
SCALES = [0.5, 0.75, 1.0, 1.25]
CONFIG = MultiBacktestConfig(initial_cash=10_000.0)


def slice_frames(frames: dict[str, pl.DataFrame], start, end) -> dict[str, pl.DataFrame]:  # noqa: ANN001
    out = {}
    for s, df in frames.items():
        part = df.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))
        if part.height > 30:
            out[s] = part
    return out


def wf_stream(frames: dict[str, pl.DataFrame], top_k: int) -> pl.DataFrame:
    master = frames["BTCUSDT"]["timestamp"].to_list()
    stitched = []
    level = 10_000.0
    chosen = []
    for w in walk_forward_windows(len(master), TRAIN, TEST):
        t0 = master[w.train_start]
        t1 = master[w.train_end - 1] + timedelta(days=1)
        t2 = master[w.test_end - 1] + timedelta(days=1)
        best_param, best_sharpe = GRID[0], float("-inf")
        for lookback in GRID:
            train = run_multi_backtest(
                slice_frames(frames, t0, t1),
                VolTargetRotation(lookback, top_k=top_k),
                config=CONFIG,
                warmup_bars=max(lookback, 30) + 1,
            )
            if train.equity_curve.height < 30:
                continue
            sharpe = compute_metrics(train.equity_curve, [], Interval.D1).sharpe
            if sharpe > best_sharpe:
                best_param, best_sharpe = lookback, sharpe
        chosen.append(best_param)
        warm = t1 - timedelta(days=max(best_param, 30) + 11)
        test = run_multi_backtest(
            slice_frames(frames, warm, t2),
            VolTargetRotation(best_param, top_k=top_k),
            config=CONFIG,
            warmup_bars=max(best_param, 30) + 1,
        )
        curve = test.equity_curve.filter(pl.col("timestamp") >= t1)
        if curve.height == 0:
            continue
        first, last = curve["equity"][0], curve["equity"][-1]
        stitched.append(curve.with_columns(pl.col("equity") * (level / first)))
        level *= last / first
    print(f"  K={top_k}: chosen L per window: {chosen}")
    return pl.concat(stitched)


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    frames = {}
    for symbol in universe:
        try:
            frames[symbol] = store.read(symbol, Interval.D1)
        except FileNotFoundError:
            print(f"  (skipping {symbol}: no data)")
    print(f"universe loaded: {len(frames)} symbols\n")

    eligible = False
    for top_k in (2, 5):
        oos = wf_stream(frames, top_k)
        m = compute_metrics(oos, [], Interval.D1)
        returns = oos["equity"].pct_change().drop_nulls()
        pp = (returns.mean() or 0.0) / (returns.std() or 1.0)
        skew, kurt = returns.skew(), returns.kurtosis()
        # DSR trial variance proxy: the two K variants' pp-sharpes get
        # computed as we go; for simplicity use a fixed small variance is NOT
        # acceptable — use variance of per-window growth-implied sharpes? Use
        # the two fixed-L full runs like prior studies:
        trial_pp = []
        oos_start = oos["timestamp"][0]
        for lookback in GRID:
            fixed = run_multi_backtest(
                frames,
                VolTargetRotation(lookback, top_k=top_k),
                config=CONFIG,
                warmup_bars=max(lookback, 30) + 1,
            )
            curve = fixed.equity_curve.filter(pl.col("timestamp") >= oos_start)
            r = curve["equity"].pct_change().drop_nulls()
            trial_pp.append((r.mean() or 0.0) / (r.std() or 1.0))
        dsr = probabilistic_sharpe_ratio(
            pp,
            n_obs=oos.height,
            skew=skew if isinstance(skew, float) else 0.0,
            kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
            benchmark_sharpe=expected_max_sharpe(N_TRIALS, statistics.variance(trial_pp)),
        )
        print(
            f"  K={top_k}: OOS {oos.height}d  Sharpe {m.sharpe:.2f}  CAGR {m.cagr_pct:+.1f}%  "
            f"MDD {m.max_drawdown_pct:.1f}%  DSR({N_TRIALS}) {dsr:.3f}"
        )
        best = None
        for scale in SCALES:
            r = simulate_evaluation(returns.to_list(), FIRM_RULES, scale, n_paths=20_000)
            if best is None or r.pass_rate > best.pass_rate:
                best = r
        assert best is not None
        print(
            f"  K={top_k}: best prop pass {best.pass_rate:.1%} @ {best.risk_scale}x "
            f"(median {best.median_days_to_pass}d)"
        )
        bar1 = m.sharpe >= 0.85 * BASELINE_8COIN_SHARPE
        bar2 = best.pass_rate >= 0.45
        print(
            f"  K={top_k}: bar1 (Sharpe>= {0.85 * BASELINE_8COIN_SHARPE:.2f}) "
            f"{'PASS' if bar1 else 'fail'}; bar2 (prop>=45%) {'PASS' if bar2 else 'fail'}\n"
        )
        eligible = eligible or (bar1 and bar2)

    print(
        "VERDICT: "
        + (
            "SURVIVORSHIP CAVEAT DOWNGRADED — rotation holds up on the wide universe"
            if eligible
            else "rotation DOES NOT hold up — hyp 11 flagged survivor-inflated"
        )
    )


if __name__ == "__main__":
    main()
