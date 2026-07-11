"""Hypothesis 12: 50/50 combined book — validation on the common OOS window.

    .venv/Scripts/python scripts/h12_combined_study.py
"""

from __future__ import annotations

import statistics
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
from trading_bot.strategies.rotation import VolTargetRotation
from trading_bot.strategies.vol_target import VolTargetMomentum

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
TRAIN, TEST = 365, 90
N_TRIALS = 57
FIRM_RULES = PropFirmRules(
    "1step-5k-static", 5_000.0, 0.10, None, 0.03, None, 51.80, static_max_loss_pct=0.06
)
SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]


def rotation_stream(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    master = frames["BTCUSDT"]["timestamp"].to_list()
    config = MultiBacktestConfig(initial_cash=10_000.0)
    stitched = []
    level = 10_000.0
    for w in walk_forward_windows(len(master), TRAIN, TEST):
        t0 = master[w.train_start]
        t1 = master[w.train_end - 1] + timedelta(days=1)
        t2 = master[w.test_end - 1] + timedelta(days=1)
        best_param, best_sharpe = 30, float("-inf")
        for lookback in (30, 90):
            sliced = {
                s: df.filter((pl.col("timestamp") >= t0) & (pl.col("timestamp") < t1))
                for s, df in frames.items()
            }
            sliced = {s: d for s, d in sliced.items() if d.height > 0}
            train = run_multi_backtest(
                sliced,
                VolTargetRotation(lookback),
                config=config,
                warmup_bars=max(lookback, 30) + 1,
            )
            if train.equity_curve.height < 30:
                continue
            sharpe = compute_metrics(train.equity_curve, [], Interval.D1).sharpe
            if sharpe > best_sharpe:
                best_param, best_sharpe = lookback, sharpe
        warm = t1 - timedelta(days=max(best_param, 30) + 11)
        sliced = {
            s: df.filter((pl.col("timestamp") >= warm) & (pl.col("timestamp") < t2))
            for s, df in frames.items()
        }
        sliced = {s: d for s, d in sliced.items() if d.height > 0}
        test = run_multi_backtest(
            sliced,
            VolTargetRotation(best_param),
            config=config,
            warmup_bars=max(best_param, 30) + 1,
        )
        curve = test.equity_curve.filter(pl.col("timestamp") >= t1)
        if curve.height == 0:
            continue
        first, last = curve["equity"][0], curve["equity"][-1]
        stitched.append(curve.with_columns(pl.col("equity") * (level / first)))
        level *= last / first
    oos = pl.concat(stitched)
    return oos.select(
        "timestamp", (pl.col("equity").pct_change().fill_null(0.0)).alias("rot")
    )


def v1_stream(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    per_symbol = []
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
        per_symbol.append(
            outcome.oos_equity.select(
                "timestamp", pl.col("equity").pct_change().fill_null(0.0).alias(symbol)
            )
        )
    wide = per_symbol[0]
    for part in per_symbol[1:]:
        wide = wide.join(part, on="timestamp", how="inner")
    return wide.select(
        "timestamp", pl.mean_horizontal([pl.col(s) for s in SYMBOLS]).alias("v1")
    )


def summarize(name: str, returns: pl.Series, timestamps: pl.Series) -> tuple[float, float]:
    curve = pl.DataFrame(
        {
            "timestamp": timestamps,
            "equity": (1.0 + returns).cum_prod() * 10_000.0,
            "exposure": pl.Series([1.0] * returns.len()),
        }
    )
    m = compute_metrics(curve, [], Interval.D1)
    print(
        f"{name:<10} Sharpe {m.sharpe:.2f}  CAGR {m.cagr_pct:+.1f}%  "
        f"MDD {m.max_drawdown_pct:.1f}%"
    )
    return m.sharpe, m.max_drawdown_pct


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    frames = {s: store.read(s, Interval.D1) for s in SYMBOLS}

    v1 = v1_stream(frames)
    rot = rotation_stream(frames)
    joined = v1.join(rot, on="timestamp", how="inner").sort("timestamp")
    joined = joined.with_columns(combined=(pl.col("v1") + pl.col("rot")) / 2.0)
    print(
        f"common OOS window: {joined.height} days, "
        f"{joined['timestamp'][0]:%Y-%m-%d} .. {joined['timestamp'][-1]:%Y-%m-%d}"
    )
    corr = joined.select(pl.corr("v1", "rot")).item()
    print(f"sleeve correlation: {corr:.2f}\n")

    s_v1, dd_v1 = summarize("v1", joined["v1"], joined["timestamp"])
    s_rot, dd_rot = summarize("rotation", joined["rot"], joined["timestamp"])
    s_comb, dd_comb = summarize("combined", joined["combined"], joined["timestamp"])

    combined = joined["combined"]
    pp = (combined.mean() or 0.0) / (combined.std() or 1.0)
    skew = combined.skew()
    kurt = combined.kurtosis()
    trial_pp = [
        (joined[c].mean() or 0.0) / (joined[c].std() or 1.0) for c in ("v1", "rot")
    ]
    dsr = probabilistic_sharpe_ratio(
        pp,
        n_obs=joined.height,
        skew=skew if isinstance(skew, float) else 0.0,
        kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, statistics.variance(trial_pp)),
    )
    print(f"\ncombined DSR vs {N_TRIALS}-trial ledger: {dsr:.3f}")

    print("\nprop-sim, real firm 1-step static rules:")
    best = None
    for scale in SCALES:
        r = simulate_evaluation(combined.to_list(), FIRM_RULES, scale, n_paths=20_000)
        print("  " + r.to_text())
        if best is None or r.pass_rate > best.pass_rate:
            best = r
    assert best is not None

    best_sleeve = max(s_v1, s_rot)
    bar1 = s_comb > best_sleeve or (
        s_comb >= 0.95 * best_sleeve and dd_comb > dd_v1 and dd_comb > dd_rot
    )
    bar2 = best.pass_rate >= 0.45
    print(
        f"\nVERDICT: bar1 (Sharpe vs best sleeve) {'PASS' if bar1 else 'fail'}; "
        f"bar2 (prop >= 45%) {best.pass_rate:.1%} {'PASS' if bar2 else 'fail'} -> "
        f"{'ELIGIBLE FOR PAPER' if bar1 and bar2 else 'NOT eligible'}"
    )


if __name__ == "__main__":
    main()
