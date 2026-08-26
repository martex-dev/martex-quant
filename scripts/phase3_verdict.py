"""Phase 3 verdict supplement for the winning family (daily TSMOM).

Two analyses, both derived from hypothesis 02's protocol:

1. Fixed-lookback robustness: OOS annualized Sharpe per L per symbol —
   a real edge should be broadly positive across the grid, not one spike.
2. Equal-weight portfolio: hypothesis 02's walk-forward OOS curves across
   all 8 symbols, averaged (daily rebalance to equal weight). TSMOM is
   classically a PORTFOLIO strategy; single-asset noise should diversify.
   This is one additional pre-declared trial (total trial count: 23).
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
from martex_quant.strategies.momentum import TimeSeriesMomentum

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
GRID = [7, 14, 30, 60, 90, 180]
CONFIG = BacktestConfig(initial_cash=10_000.0)
STORE = ParquetStore(Path("data/lake"))


def ann_sharpe(curve: pl.DataFrame) -> float:
    return compute_metrics(curve, [], Interval.D1).sharpe


def main() -> None:
    # --- 1. fixed-lookback robustness --------------------------------------
    print("Fixed-lookback OOS annualized Sharpe (daily TSMOM, OOS = last 12x90d)\n")
    frames: dict[str, pl.DataFrame] = {}
    for symbol in SYMBOLS:
        frames[symbol] = STORE.read(symbol, Interval.D1)

    print(f"{'L':>4} " + "".join(f"{s[:-4]:>8}" for s in SYMBOLS) + f"{'median':>8}")
    for lookback in GRID:
        sharpes = []
        for symbol in SYMBOLS:
            df = frames[symbol]
            result = run_backtest(
                df, symbol, TimeSeriesMomentum(lookback), config=CONFIG, warmup_bars=lookback + 1
            )
            # Same OOS span as the walk-forward study: last 1080 daily bars.
            curve = result.equity_curve.tail(1080)
            sharpes.append(ann_sharpe(curve))
        print(
            f"{lookback:>4} "
            + "".join(f"{s:>8.2f}" for s in sharpes)
            + f"{statistics.median(sharpes):>8.2f}"
        )

    # --- 2. equal-weight portfolio of the walk-forward OOS curves ----------
    print("\nEqual-weight 8-symbol portfolio of hypothesis-02 walk-forward OOS:\n")
    daily_returns: list[pl.Series] = []
    trial_curves: dict[int, list[pl.Series]] = {lb: [] for lb in GRID}
    for symbol in SYMBOLS:
        outcome = walk_forward_backtest(
            df=frames[symbol],
            symbol=symbol,
            interval=Interval.D1,
            param_grid=GRID,
            strategy_factory=lambda p: TimeSeriesMomentum(int(p)),
            warmup_of=lambda p: int(p) + 1,
            train_size=365,
            test_size=90,
            config=CONFIG,
        )
        daily_returns.append(outcome.oos_equity["equity"].pct_change().fill_null(0.0))
        for lookback in GRID:
            fixed = run_backtest(
                frames[symbol],
                symbol,
                TimeSeriesMomentum(lookback),
                config=CONFIG,
                warmup_bars=lookback + 1,
            )
            trial_curves[lookback].append(
                fixed.equity_curve.tail(1080)["equity"].pct_change().fill_null(0.0)
            )

    n = min(s.len() for s in daily_returns)
    port_returns = sum((s.tail(n) for s in daily_returns), start=pl.Series([0.0] * n)) / len(
        SYMBOLS
    )
    equity = 10_000.0 * (1.0 + port_returns).cum_prod()
    curve = pl.DataFrame(
        {
            "timestamp": frames["BTCUSDT"].tail(n)["timestamp"],
            "equity": equity,
            "exposure": pl.Series([1.0] * n),
        }
    )
    m = compute_metrics(curve, [], Interval.D1)
    print(m.to_text())

    # Portfolio-level trial sharpes (per-period) for the DSR benchmark:
    trial_pp_sharpes = []
    for lookback in GRID:
        k = min(s.len() for s in trial_curves[lookback])
        pr = sum((s.tail(k) for s in trial_curves[lookback]), start=pl.Series([0.0] * k)) / len(
            SYMBOLS
        )
        mean, std = pr.mean(), pr.std()
        trial_pp_sharpes.append(
            mean / std if isinstance(mean, float) and isinstance(std, float) and std > 0 else 0.0
        )

    pp = port_returns.tail(n)
    mean, std = pp.mean(), pp.std()
    assert isinstance(mean, float) and isinstance(std, float)
    skew = pp.skew()
    kurt = pp.kurtosis()
    for n_trials, label in [(6, "grid only"), (23, "ALL Phase 3 specs")]:
        dsr = probabilistic_sharpe_ratio(
            mean / std,
            n_obs=n,
            skew=skew if isinstance(skew, float) else 0.0,
            kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
            benchmark_sharpe=expected_max_sharpe(n_trials, statistics.variance(trial_pp_sharpes)),
        )
        print(f"portfolio DSR (n_trials={n_trials}, {label}): {dsr:.3f}")


if __name__ == "__main__":
    main()
