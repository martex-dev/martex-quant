"""The event-driven backtest loop.

Per bar t, in this exact order:

1. Broker fills orders submitted at t-1, at bar t's OPEN (one-bar latency).
2. History advances: bar t becomes the newest closed bar.
3. Strategy sees history only and emits a target exposure.
4. Risk policy adjusts (gate, not suggestion).
5. Portfolio turns an exposure CHANGE into an order for t+1.
6. Equity is recorded at bar t's close.

Signal on the close, execution on the next open: the strategy can never act
on information from the bar it trades into. Orders pending after the final
bar are dropped (reported on the result), and the last position is marked at
the final close.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from trading_bot.backtesting.history import History
from trading_bot.core.events import Fill, bars_from_frame
from trading_bot.execution.simulated import ExecutionConfig, SimulatedBroker
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.risk_management.policy import PassthroughPolicy, RiskPolicy
from trading_bot.strategies.base import Strategy


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 10_000.0
    allow_short: bool = False
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    config: BacktestConfig
    equity_curve: pl.DataFrame  # timestamp, equity, exposure
    fills: list[Fill]
    unfilled_orders: int

    @property
    def initial_equity(self) -> float:
        return self.config.initial_cash

    @property
    def final_equity(self) -> float:
        value = self.equity_curve["equity"][-1]
        assert isinstance(value, float)
        return value

    @property
    def total_fees(self) -> float:
        return sum(f.fee for f in self.fills)


def run_backtest(
    df: pl.DataFrame,
    symbol: str,
    strategy: Strategy,
    config: BacktestConfig | None = None,
    risk_policy: RiskPolicy | None = None,
    warmup_bars: int = 0,
) -> BacktestResult:
    """Run one strategy over one instrument's canonical OHLCV frame.

    ``warmup_bars``: the first N bars feed history only — no signals, no
    orders, no equity recording. Lets a strategy start a window with its
    indicators already primed on PAST data (walk-forward test windows would
    otherwise sit forcibly flat for the first lookback's worth of bars).
    """
    if df.height == 0:
        raise ValueError("cannot backtest an empty frame")
    if not 0 <= warmup_bars < df.height:
        raise ValueError(f"warmup_bars must be in [0, {df.height}), got {warmup_bars}")
    cfg = config if config is not None else BacktestConfig()
    risk = risk_policy if risk_policy is not None else PassthroughPolicy()

    bars = bars_from_frame(df)
    history = History(bars)
    broker = SimulatedBroker(cfg.execution)
    portfolio = Portfolio(symbol, cfg.initial_cash, allow_short=cfg.allow_short)

    timestamps = []
    equities = []
    exposures = []
    all_fills: list[Fill] = []

    for i, bar in enumerate(bars):
        for fill in broker.execute_pending(bar):
            portfolio.apply_fill(fill)
            all_fills.append(fill)

        history.advance()
        if i < warmup_bars:
            continue  # priming history only; the strategy is not consulted
        target = strategy.on_bar(history)
        allowed = risk.adjust(target, portfolio.equity(bar.close), cfg.initial_cash, bar.timestamp)
        order = portfolio.target_order(allowed, bar)
        if order is not None:
            broker.submit(order)

        equity = portfolio.equity(bar.close)
        timestamps.append(bar.timestamp)
        equities.append(equity)
        exposures.append(portfolio.position * bar.close / equity if equity > 0 else 0.0)

    equity_curve = pl.DataFrame(
        {"timestamp": timestamps, "equity": equities, "exposure": exposures}
    )
    return BacktestResult(
        symbol=symbol,
        config=cfg,
        equity_curve=equity_curve,
        fills=all_fills,
        unfilled_orders=len(broker.pending),
    )
