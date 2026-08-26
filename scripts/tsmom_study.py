"""Phase 3, Study 1: time-series momentum walk-forward across the lake.

Reproducible: run with  .venv/Scripts/python scripts/tsmom_study.py
Protocol pre-registered in docs/hypotheses/01-time-series-momentum.md.

Per symbol:
- walk-forward (1y train, 90d test, tiled OOS), selection by train Sharpe
- buy-and-hold benchmark over the IDENTICAL OOS span, same cost model
- deflated Sharpe: OOS per-period Sharpe tested against the expected max
  Sharpe of 6 unskilled trials (the grid size), with skew/kurtosis penalty
"""

from __future__ import annotations

import statistics
from pathlib import Path

import polars as pl

from martex_quant.backtesting.engine import BacktestConfig, run_backtest
from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.backtesting.research import walk_forward_backtest
from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.stats.significance import per_period_sharpe
from martex_quant.strategies.benchmark import BuyAndHold
from martex_quant.strategies.momentum import TimeSeriesMomentum

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
GRID = [168, 336, 504, 720, 1440, 2160]  # hours: 1w, 2w, 3w, 30d, 60d, 90d
TRAIN = 8766  # 1 year of 1h bars
TEST = 2160  # 90 days
INTERVAL = Interval.H1
CONFIG = BacktestConfig(initial_cash=10_000.0)


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    print(f"grid={GRID}  train={TRAIN} bars  test={TEST} bars\n")
    header = (
        f"{'symbol':<9} {'OOS ret':>9} {'OOS shp':>8} {'OOS MDD':>9} {'in mkt':>7} "
        f"{'B&H ret':>9} {'B&H shp':>8} {'B&H MDD':>9} {'DSR':>6}  chosen L per window"
    )
    print(header)
    print("-" * len(header))

    dsr_values = []
    beat_bh = 0
    for symbol in SYMBOLS:
        df = store.read(symbol, INTERVAL)
        outcome = walk_forward_backtest(
            df,
            symbol,
            INTERVAL,
            param_grid=GRID,
            strategy_factory=TimeSeriesMomentum,
            warmup_of=lambda p: p,
            train_size=TRAIN,
            test_size=TEST,
            config=CONFIG,
        )
        oos = outcome.oos_equity
        m = compute_metrics(oos, [], INTERVAL)

        # Buy-and-hold over the identical OOS span, same engine and costs.
        oos_start = oos["timestamp"][0]
        span = df.filter(pl.col("timestamp") >= oos_start)
        bh = run_backtest(span, symbol, BuyAndHold(), config=CONFIG)
        bh_m = compute_metrics(bh.equity_curve, bh.fills, INTERVAL)

        # Deflated Sharpe: trial variance from each FIXED lookback run over
        # the same OOS span (what "no skill, 6 tries" could have produced).
        trial_sharpes = []
        for lookback in GRID:
            fixed = run_backtest(
                df, symbol, TimeSeriesMomentum(lookback), config=CONFIG, warmup_bars=lookback
            )
            curve = fixed.equity_curve.filter(pl.col("timestamp") >= oos_start)
            trial_sharpes.append(per_period_sharpe(curve["equity"]))
        sr0 = expected_max_sharpe(len(GRID), statistics.variance(trial_sharpes))

        oos_returns = oos["equity"].pct_change().drop_nulls()
        skew = oos_returns.skew()
        kurt = oos_returns.kurtosis()  # excess (Fisher)
        dsr = probabilistic_sharpe_ratio(
            per_period_sharpe(oos["equity"]),
            n_obs=oos.height,
            skew=skew if isinstance(skew, float) else 0.0,
            kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
            benchmark_sharpe=sr0,
        )
        dsr_values.append(dsr)
        if m.sharpe > bh_m.sharpe:
            beat_bh += 1

        chosen = ",".join(str(w.chosen_param) for w in outcome.windows)
        print(
            f"{symbol:<9} {m.total_return_pct:>8.1f}% {m.sharpe:>8.2f} "
            f"{m.max_drawdown_pct:>8.1f}% {m.time_in_market_pct:>6.1f}% "
            f"{bh_m.total_return_pct:>8.1f}% {bh_m.sharpe:>8.2f} "
            f"{bh_m.max_drawdown_pct:>8.1f}% {dsr:>6.3f}  {chosen}"
        )

    print(
        f"\n{beat_bh}/{len(SYMBOLS)} symbols beat buy-and-hold on Sharpe; "
        f"median DSR = {statistics.median(dsr_values):.3f} "
        f"(pre-registered bar: > 0.95 on a broad, multi-symbol basis)"
    )


if __name__ == "__main__":
    main()
