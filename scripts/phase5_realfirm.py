"""Phase 5: the USER'S ACTUAL prop-firm options, simulated.

    .venv/Scripts/python scripts/phase5_realfirm.py

Option 1 (1-step, 5k):  target +10%, max loss $300 (6%), daily 3%,
                        no time limit, 1:30 leverage. Fee ASSUMED $65.
Option 2 (2-step, 5k):  stage 1 +10%, stage 2 +5%, max loss $500 (10%)
                        per stage, daily 5%, no limit, 1:100. Fee ASSUMED $45.

Unknowns flagged: whether "max loss" is STATIC (floor at initial-$X) or
TRAILING (follows equity peak) — both simulated; exact fees — assumed,
breakevens reported so the answer survives fee uncertainty. Leverage caps
(30x/100x) are far above any sizing simulated and never bind.

Strategies: the final-selection pair — Donchian breakout (eval engine)
and vol-target momentum (funded engine) — as EW 8-symbol portfolios.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from pathlib import Path

import polars as pl

from trading_bot.backtesting.engine import BacktestConfig
from trading_bot.backtesting.research import walk_forward_backtest
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.risk_management.prop_sim import (
    EvalResult,
    PropFirmRules,
    simulate_evaluation,
    simulate_two_step,
)
from trading_bot.strategies.base import Strategy
from trading_bot.strategies.breakout import DonchianBreakout
from trading_bot.strategies.vol_target import VolTargetMomentum

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
STORE = ParquetStore(Path("data/lake"))
CONFIG = BacktestConfig(initial_cash=10_000.0)
SCALES = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
FUNDED_VALUES = [250.0, 500.0, 1000.0]  # a 5k funded account is worth far less than a 50k one

FEE_1STEP = 65.0  # ASSUMED — verify with the firm
FEE_2STEP = 45.0  # ASSUMED — user says 2-step is cheaper


def build_returns(
    grid: list[int], factory: Callable[[float], Strategy], warmup_of: Callable[[float], int]
) -> list[float]:
    series: list[pl.Series] = []
    for symbol in SYMBOLS:
        outcome = walk_forward_backtest(
            STORE.read(symbol, Interval.D1),
            symbol,
            Interval.D1,
            grid,
            factory,
            warmup_of,
            365,
            90,
            config=CONFIG,
        )
        series.append(outcome.oos_equity["equity"].pct_change().fill_null(0.0))
    n = min(s.len() for s in series)
    total = pl.Series([0.0] * n)
    for s in series:
        total = total + s.tail(n)
    return list((total / len(series)).to_list())


def option1_rules(static: bool, name: str) -> PropFirmRules:
    return PropFirmRules(
        name=name,
        account_size=5_000.0,
        profit_target_pct=0.10,
        trailing_dd_pct=None if static else 0.06,
        daily_loss_pct=0.03,
        max_days=None,
        evaluation_fee=FEE_1STEP,
        static_max_loss_pct=0.06 if static else None,
    )


def option2_stages(static: bool) -> tuple[PropFirmRules, PropFirmRules]:
    def stage(target: float, tag: str) -> PropFirmRules:
        return PropFirmRules(
            name=f"2step-{tag}",
            account_size=5_000.0,
            profit_target_pct=target,
            trailing_dd_pct=None if static else 0.10,
            daily_loss_pct=0.05,
            max_days=None,
            evaluation_fee=FEE_2STEP,
            static_max_loss_pct=0.10 if static else None,
        )

    return stage(0.10, "s1"), stage(0.05, "s2")


def report(result: EvalResult, fee: float) -> str:
    if result.pass_rate == 0.0:
        return f"    {result.risk_scale:>4.2f}x: pass 0% — dead config"
    evs = " ".join(f"${v:.0f}->{result.expected_value(v):+,.0f}" for v in FUNDED_VALUES)
    breakeven = fee / result.pass_rate
    days = result.median_days_to_pass
    ev_day = f", EV/day@$500 {result.expected_value(500.0) / days:+.1f}" if days else ""
    return (
        f"    {result.risk_scale:>4.2f}x: pass {result.pass_rate:.1%} "
        f"(CI {result.pass_ci_low:.1%}-{result.pass_ci_high:.1%}), bust {result.fail_rate:.1%}, "
        f"median {days}d | EV {evs} | breakeven ${breakeven:.0f}{ev_day}"
    )


def main() -> None:
    for label, grid, factory, warmup_of in [
        (
            "DONCHIAN (eval engine)",
            [10, 20, 40, 55, 80, 120],
            lambda p: DonchianBreakout(int(p)),
            lambda p: int(p) + 1,
        ),
        (
            "VOL-TARGET (funded engine)",
            [7, 14, 30, 60, 90, 180],
            lambda p: VolTargetMomentum(int(p)),
            lambda p: max(int(p), 30) + 1,
        ),
    ]:
        returns = build_returns(grid, factory, warmup_of)
        ann_vol = statistics.stdev(returns) * (365**0.5)
        print(f"\n########## {label}: {len(returns)}d OOS, ann.vol {ann_vol:.1%} ##########")
        for static in (True, False):
            variant = "STATIC max loss" if static else "TRAILING max loss"
            print(f"\n  == Option 1 (1-step, $300 loss, 3% daily) — {variant} ==")
            rules = option1_rules(static, f"1step-{'static' if static else 'trail'}")
            for scale in SCALES:
                print(report(simulate_evaluation(returns, rules, scale, 20_000), FEE_1STEP))
            print(f"\n  == Option 2 (2-step, $500 loss, 5% daily) — {variant} ==")
            s1, s2 = option2_stages(static)
            for scale in SCALES:
                print(report(simulate_two_step(returns, s1, s2, scale, 20_000), FEE_2STEP))


if __name__ == "__main__":
    main()
