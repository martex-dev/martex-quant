"""Hypothesis 11 strategy-grade study: dual-momentum rotation, walk-forward.

    .venv/Scripts/python scripts/h11_strategy_study.py

Spec pre-registered in docs/hypotheses/11-cross-sectional-rotation.md.
"""

from __future__ import annotations

import statistics
import sys
from datetime import timedelta
from pathlib import Path

import polars as pl

from trading_bot.backtesting.engine import BacktestConfig
from trading_bot.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from trading_bot.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from trading_bot.backtesting.research import walk_forward_backtest
from trading_bot.backtesting.walkforward import walk_forward_windows
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.risk_management.prop_sim import PropFirmRules, simulate_evaluation
from trading_bot.strategies.rotation import DualMomentumRotation, VolTargetRotation
from trading_bot.strategies.vol_target import VolTargetMomentum

SIZED = "--sized" in sys.argv


def make_strategy(lookback: int):  # noqa: ANN201
    return VolTargetRotation(lookback) if SIZED else DualMomentumRotation(lookback)


def warmup_of(lookback: int) -> int:
    return (max(lookback, 30) if SIZED else lookback) + 1


SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
GRID = [30, 90]
TRAIN, TEST = 365, 90
N_TRIALS = 55
CONFIG = MultiBacktestConfig(initial_cash=10_000.0)
FIRM_RULES = PropFirmRules(
    "1step-5k-static", 5_000.0, 0.10, None, 0.03, None, 51.80, static_max_loss_pct=0.06
)
SCALES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


def slice_frames(
    frames: dict[str, pl.DataFrame], start: object, end: object
) -> dict[str, pl.DataFrame]:
    out = {}
    for s, df in frames.items():
        part = df.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))
        if part.height > 0:
            out[s] = part
    return out


def sharpe_of(curve: pl.DataFrame) -> float:
    if curve.height < 30:
        return float("-inf")
    return compute_metrics(curve, [], Interval.D1).sharpe


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    frames = {s: store.read(s, Interval.D1) for s in SYMBOLS}
    master = frames["BTCUSDT"]["timestamp"].to_list()

    windows = walk_forward_windows(len(master), TRAIN, TEST)
    stitched: list[pl.DataFrame] = []
    level = 10_000.0
    chosen_list = []
    for w in windows:
        t0, t1 = master[w.train_start], master[w.train_end - 1] + timedelta(days=1)
        t2 = master[w.test_end - 1] + timedelta(days=1)
        best_param, best_sharpe = None, float("-inf")
        for lookback in GRID:
            train = run_multi_backtest(
                slice_frames(frames, t0, t1),
                make_strategy(lookback),
                config=CONFIG,
                warmup_bars=warmup_of(lookback),
            )
            s = sharpe_of(train.equity_curve)
            if s > best_sharpe:
                best_param, best_sharpe = lookback, s
        assert best_param is not None
        chosen_list.append(best_param)

        warm_start = t1 - timedelta(days=warmup_of(best_param) + 10)
        test = run_multi_backtest(
            slice_frames(frames, warm_start, t2),
            make_strategy(best_param),
            config=CONFIG,
            warmup_bars=warmup_of(best_param),
        )
        curve = test.equity_curve.filter(pl.col("timestamp") >= t1)
        if curve.height == 0:
            continue
        first, last = curve["equity"][0], curve["equity"][-1]
        stitched.append(curve.with_columns(pl.col("equity") * (level / first)))
        level *= last / first

    oos = pl.concat(stitched)
    m = compute_metrics(oos, [], Interval.D1)
    returns = oos["equity"].pct_change().drop_nulls()
    pp_sharpe = (returns.mean() or 0.0) / (returns.std() or 1.0)

    print(f"variant: {'SIZED (vol-target)' if SIZED else 'RAW'}")
    print(f"walk-forward OOS: {oos.height} days, chosen L per window: {chosen_list}")
    print(m.to_text())

    # DSR benchmark: fixed-L full-period runs over the same OOS span.
    oos_start = oos["timestamp"][0]
    trial_sharpes = []
    for lookback in GRID:
        fixed = run_multi_backtest(
            frames, make_strategy(lookback), config=CONFIG, warmup_bars=warmup_of(lookback)
        )
        curve = fixed.equity_curve.filter(pl.col("timestamp") >= oos_start)
        r = curve["equity"].pct_change().drop_nulls()
        trial_sharpes.append((r.mean() or 0.0) / (r.std() or 1.0))
    skew = returns.skew()
    kurt = returns.kurtosis()
    dsr = probabilistic_sharpe_ratio(
        pp_sharpe,
        n_obs=oos.height,
        skew=skew if isinstance(skew, float) else 0.0,
        kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, statistics.variance(trial_sharpes)),
    )
    print(f"DSR vs {N_TRIALS}-trial ledger: {dsr:.3f}")

    # Correlation with the deployed V1 vol-target stream (tail-aligned).
    v1_series: list[pl.Series] = []
    for symbol in SYMBOLS:
        outcome = walk_forward_backtest(
            frames[symbol],
            symbol,
            Interval.D1,
            [7, 14, 30, 60, 90, 180],
            lambda p: VolTargetMomentum(int(p)),
            lambda p: max(int(p), 30) + 1,
            TRAIN,
            TEST,
            config=BacktestConfig(initial_cash=10_000.0),
        )
        v1_series.append(outcome.oos_equity["equity"].pct_change().fill_null(0.0))
    n1 = min(s.len() for s in v1_series)
    v1 = pl.Series([0.0] * n1)
    for s in v1_series:
        v1 = v1 + s.tail(n1)
    v1 = v1 / len(v1_series)
    rot = oos["equity"].pct_change().fill_null(0.0)
    k = min(v1.len(), rot.len())
    corr_df = pl.DataFrame({"a": v1.tail(k), "b": rot.tail(k)})
    corr = corr_df.select(pl.corr("a", "b")).item()
    v1_m = compute_metrics(
        pl.DataFrame(
            {
                "timestamp": oos["timestamp"].tail(k),
                "equity": (1.0 + v1.tail(k)).cum_prod() * 10_000.0,
                "exposure": pl.Series([1.0] * k),
            }
        ),
        [],
        Interval.D1,
    )
    print(f"correlation with V1 vol-target (last {k}d overlap): {corr:.2f}")
    print(f"V1 Sharpe on same overlap: {v1_m.sharpe:.2f} vs rotation {m.sharpe:.2f}")

    print("\nprop-sim, REAL firm 1-step static rules ($51.80):")
    best = None
    for scale in SCALES:
        r = simulate_evaluation(rot.to_list(), FIRM_RULES, scale, n_paths=20_000)
        print("  " + r.to_text())
        if best is None or r.pass_rate > best.pass_rate:
            best = r
    assert best is not None

    bar1 = m.sharpe >= v1_m.sharpe or (m.sharpe >= 0.85 * v1_m.sharpe and corr < 0.7)
    bar2 = best.pass_rate >= 0.35
    print(
        f"\nVERDICT vs pre-registered bars: sharpe/diversification {'PASS' if bar1 else 'fail'}; "
        f"prop pass {best.pass_rate:.1%} @ {best.risk_scale}x {'PASS' if bar2 else 'fail'} -> "
        f"{'ELIGIBLE FOR PAPER TRADING' if bar1 and bar2 else 'NOT eligible'}"
    )


if __name__ == "__main__":
    main()
