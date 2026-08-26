"""Multi-asset event-driven backtest: one portfolio brain across symbols.

Same honesty guarantees as the single-asset engine: per-symbol History
views (look-ahead structurally impossible), decisions at the close, fills
at the NEXT bar's open through the same pessimistic cost model, warmup
support. Symbols may list at different dates — a symbol joins the
decision set once it has bars.

Weights contract: a MultiAssetStrategy returns {symbol: fraction of TOTAL
portfolio equity}, long-only, sum <= 1. Unallocated fraction is cash.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import polars as pl

from martex_quant.backtesting.history import History
from martex_quant.core.events import Bar, Fill, Order, Side, bars_from_frame
from martex_quant.execution.simulated import ExecutionConfig, SimulatedBroker

_REBALANCE_DUST = 0.002  # skip order if |delta notional| < 0.2% of equity


class MultiAssetStrategy(ABC):
    @abstractmethod
    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        """Fractions of total equity per symbol (long-only, sum <= 1).

        ``histories`` contains only symbols with at least one closed bar.
        Omitted symbols mean weight 0.
        """


@dataclass(frozen=True)
class MultiBacktestConfig:
    initial_cash: float = 10_000.0
    execution: ExecutionConfig | None = None


@dataclass(frozen=True)
class MultiResult:
    equity_curve: pl.DataFrame  # timestamp, equity, gross_exposure
    fills: list[Fill]
    unfilled_orders: int

    @property
    def final_equity(self) -> float:
        value = self.equity_curve["equity"][-1]
        assert isinstance(value, float)
        return value


def run_multi_backtest(
    frames: dict[str, pl.DataFrame],
    strategy: MultiAssetStrategy,
    config: MultiBacktestConfig | None = None,
    warmup_bars: int = 0,
) -> MultiResult:
    cfg = config if config is not None else MultiBacktestConfig()
    execution = cfg.execution if cfg.execution is not None else ExecutionConfig()

    bars_by_symbol: dict[str, list[Bar]] = {s: bars_from_frame(df) for s, df in frames.items()}
    if not any(bars_by_symbol.values()):
        raise ValueError("no bars in any frame")
    timeline = sorted({b.timestamp for bars in bars_by_symbol.values() for b in bars})

    # Per-symbol iteration state.
    cursors = dict.fromkeys(frames, 0)
    histories = {s: History(bars) for s, bars in bars_by_symbol.items()}
    brokers = {s: SimulatedBroker(execution) for s in frames}
    positions = dict.fromkeys(frames, 0.0)
    last_price: dict[str, float] = {}
    cash = cfg.initial_cash

    timestamps, equities, gross = [], [], []
    all_fills: list[Fill] = []

    for i, ts in enumerate(timeline):
        todays_bar: dict[str, Bar] = {}
        for symbol, bars in bars_by_symbol.items():
            c = cursors[symbol]
            if c < len(bars) and bars[c].timestamp == ts:
                todays_bar[symbol] = bars[c]
                cursors[symbol] = c + 1

        # 1. Fills at this bar's open for orders placed at the previous close.
        for symbol, bar in todays_bar.items():
            for fill in brokers[symbol].execute_pending(bar):
                cash -= fill.signed_quantity * fill.price + fill.fee
                positions[symbol] += fill.signed_quantity
                all_fills.append(fill)

        # 2. Histories advance: today's bars are now closed.
        for symbol, bar in todays_bar.items():
            histories[symbol].advance()
            last_price[symbol] = bar.close

        if i < warmup_bars:
            continue

        equity = cash + sum(
            units * last_price[s] for s, units in positions.items() if s in last_price
        )

        # 3. Decide on the closed data; orders fill at the next bar's open.
        visible = {s: h for s, h in histories.items() if len(h) > 0}
        weights = strategy.target_weights(visible)
        bad = [s for s, w in weights.items() if w < 0]
        if bad or sum(weights.values()) > 1.0 + 1e-9:
            raise ValueError(f"invalid weights (long-only, sum<=1): {weights}")

        for symbol, bar in todays_bar.items():
            target_units = weights.get(symbol, 0.0) * equity / bar.close
            delta = target_units - positions[symbol]
            if abs(delta) * bar.close < equity * _REBALANCE_DUST:
                continue
            brokers[symbol].submit(
                Order(
                    created_at=ts,
                    symbol=symbol,
                    side=Side.BUY if delta > 0 else Side.SELL,
                    quantity=abs(delta),
                )
            )

        timestamps.append(ts)
        equities.append(equity)
        invested = sum(
            abs(units) * last_price[s] for s, units in positions.items() if s in last_price
        )
        gross.append(invested / equity if equity > 0 else 0.0)

    equity_curve = pl.DataFrame({"timestamp": timestamps, "equity": equities, "exposure": gross})
    pending = sum(len(b.pending) for b in brokers.values())
    return MultiResult(equity_curve=equity_curve, fills=all_fills, unfilled_orders=pending)
