"""Final Phase 3/4 selection on extended (2017+) data.

For each surviving strategy family, build the equal-weight 8-symbol
walk-forward OOS portfolio, then score it three ways:
1. Standalone: Sharpe, MDD, DSR (grid trials and all-trials benchmark).
2. Prop-fit: best (ruleset x sizing) evaluation pass rate.
3. The decision metric for an aggressive-but-compliant pick:
   EV per DAY = EV(one attempt, $5k assumed funded value) / median days.

Trial accounting: 35 specs tried across the project to date (6 hourly
TSMOM + 6 daily TSMOM + 6 vol-filter + 4 meanrev + 6 vol-target +
6 donchian) + 3 portfolio aggregations = 38.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from pathlib import Path

import polars as pl

from trading_bot.backtesting.engine import BacktestConfig, run_backtest
from trading_bot.backtesting.metrics import (
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from trading_bot.backtesting.research import walk_forward_backtest
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.risk_management.prop_sim import PropFirmRules, simulate_evaluation
from trading_bot.strategies.base import Strategy
from trading_bot.strategies.breakout import DonchianBreakout
from trading_bot.strategies.momentum import TimeSeriesMomentum
from trading_bot.strategies.vol_target import VolTargetMomentum

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
N_TRIALS_TOTAL = 38
FUNDED_VALUE = 5_000.0
STORE = ParquetStore(Path("data/lake"))
CONFIG = BacktestConfig(initial_cash=10_000.0)

FAMILIES: dict[str, tuple[list[int], Callable[[float], Strategy], Callable[[float], int]]] = {
    "daily-tsmom": (
        [7, 14, 30, 60, 90, 180],
        lambda p: TimeSeriesMomentum(int(p)),
        lambda p: int(p) + 1,
    ),
    "vol-target": (
        [7, 14, 30, 60, 90, 180],
        lambda p: VolTargetMomentum(int(p)),
        lambda p: max(int(p), 30) + 1,
    ),
    "donchian": (
        [10, 20, 40, 55, 80, 120],
        lambda p: DonchianBreakout(int(p)),
        lambda p: int(p) + 1,
    ),
}

RULESETS = [
    PropFirmRules("GENERIC-A 50k", 50_000.0, 0.06, 0.04, 0.02, None, 170.0),
    PropFirmRules("GENERIC-B 50k", 50_000.0, 0.08, 0.03, 0.02, 90, 100.0),
]
SCALES = [0.1, 0.25, 0.5, 0.75, 1.0]


def build_portfolio_returns(
    grid: list[int],
    factory: Callable[[float], Strategy],
    warmup_of: Callable[[float], int],
) -> tuple[list[float], list[float]]:
    """Returns (walk-forward portfolio daily returns, fixed-param portfolio
    per-period trial sharpes for the DSR benchmark)."""
    wf_series: list[pl.Series] = []
    fixed_series: dict[int, list[pl.Series]] = {p: [] for p in grid}
    for symbol in SYMBOLS:
        df = STORE.read(symbol, Interval.D1)
        outcome = walk_forward_backtest(
            df, symbol, Interval.D1, grid, factory, warmup_of, 365, 90, config=CONFIG
        )
        wf_series.append(outcome.oos_equity["equity"].pct_change().fill_null(0.0))
        for param in grid:
            fixed = run_backtest(
                df, symbol, factory(param), config=CONFIG, warmup_bars=warmup_of(param)
            )
            fixed_series[param].append(fixed.equity_curve["equity"].pct_change().fill_null(0.0))

    def combine(series_list: list[pl.Series]) -> list[float]:
        n = min(s.len() for s in series_list)
        total = pl.Series([0.0] * n)
        for s in series_list:
            total = total + s.tail(n)
        return list((total / len(series_list)).to_list())

    trial_sharpes = []
    for param in grid:
        r = combine(fixed_series[param])
        mean, std = statistics.mean(r), statistics.stdev(r)
        trial_sharpes.append(mean / std if std > 0 else 0.0)
    return combine(wf_series), trial_sharpes


def main() -> None:
    print(f"universe: {len(SYMBOLS)} symbols, data from each listing (2017+), costs included")
    print(f"trial accounting: {N_TRIALS_TOTAL} specs total across the project\n")
    for name, (grid, factory, warmup_of) in FAMILIES.items():
        returns, trial_sharpes = build_portfolio_returns(grid, factory, warmup_of)
        n = len(returns)
        equity = [10_000.0]
        for r in returns:
            equity.append(equity[-1] * (1.0 + r))
        eq = pl.Series(equity[1:])
        years = n / 365.0
        total_ret = equity[-1] / 10_000.0 - 1.0
        cagr = (equity[-1] / 10_000.0) ** (1 / years) - 1.0
        mean, std = statistics.mean(returns), statistics.stdev(returns)
        sharpe = mean / std * (365**0.5) if std > 0 else 0.0
        dd = float((eq / eq.cum_max() - 1.0).min() or 0.0)

        skew = pl.Series(returns).skew()
        kurt = pl.Series(returns).kurtosis()
        dsr_all = probabilistic_sharpe_ratio(
            mean / std if std > 0 else 0.0,
            n_obs=n,
            skew=skew if isinstance(skew, float) else 0.0,
            kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
            benchmark_sharpe=expected_max_sharpe(
                N_TRIALS_TOTAL, statistics.variance(trial_sharpes)
            ),
        )

        print(f"=== {name} ===")
        print(
            f"  OOS {n}d ({years:.1f}y): total {total_ret:+.0%}, CAGR {cagr:+.1%}, "
            f"Sharpe {sharpe:.2f}, MDD {dd:.1%}, DSR(all {N_TRIALS_TOTAL} trials) {dsr_all:.3f}"
        )
        best_score = None
        best_desc = ""
        for rules in RULESETS:
            for scale in SCALES:
                result = simulate_evaluation(
                    returns, rules, risk_scale=scale, n_paths=10_000, horizon_days=365
                )
                if result.median_days_to_pass is None or result.pass_rate == 0.0:
                    continue
                ev = result.expected_value(FUNDED_VALUE)
                ev_per_day = ev / result.median_days_to_pass
                if best_score is None or ev_per_day > best_score:
                    best_score = ev_per_day
                    best_desc = (
                        f"{rules.name} @ {scale:.2f}x: pass {result.pass_rate:.1%} "
                        f"(CI {result.pass_ci_low:.1%}-{result.pass_ci_high:.1%}), "
                        f"median {result.median_days_to_pass}d, EV ${ev:+,.0f}, "
                        f"EV/day ${ev_per_day:+,.1f}"
                    )
        print(f"  prop-fit best: {best_desc}\n")


if __name__ == "__main__":
    main()
