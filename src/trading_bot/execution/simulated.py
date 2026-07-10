"""Simulated broker with a deliberately pessimistic fill model.

An order submitted on bar t fills at bar t+1's OPEN, adjusted against the
trader: half-spread plus volume-participation impact, plus taker fees.
Optimism here is the classic way backtests lie; every default leans
conservative.
"""

from __future__ import annotations

from dataclasses import dataclass

from trading_bot.core.events import Bar, Fill, Order, Side

_BPS = 1e-4


@dataclass(frozen=True)
class ExecutionConfig:
    """Cost model parameters, in basis points (1 bp = 0.01%).

    - fee_bps: taker fee on notional (Binance spot default: 10 bps)
    - half_spread_bps: half the bid/ask spread paid on every fill
    - impact_bps: extra slippage per 100% participation of the bar's volume
      (linear market-impact model, participation capped at 100%)
    """

    fee_bps: float = 10.0
    half_spread_bps: float = 1.0
    impact_bps: float = 25.0


class SimulatedBroker:
    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self.config = config if config is not None else ExecutionConfig()
        self._pending: list[Order] = []

    def submit(self, order: Order) -> None:
        self._pending.append(order)

    @property
    def pending(self) -> list[Order]:
        return list(self._pending)

    def execute_pending(self, bar: Bar) -> list[Fill]:
        """Fill all pending orders at this bar's open, costs applied."""
        fills = [self._fill(order, bar) for order in self._pending]
        self._pending.clear()
        return fills

    def _fill(self, order: Order, bar: Bar) -> Fill:
        # Zero-volume bars offer no liquidity: charge full participation.
        participation = min(order.quantity / bar.volume, 1.0) if bar.volume > 0 else 1.0
        adverse_bps = self.config.half_spread_bps + self.config.impact_bps * participation
        direction = 1.0 if order.side == Side.BUY else -1.0
        price = bar.open * (1.0 + direction * adverse_bps * _BPS)
        fee = order.quantity * price * self.config.fee_bps * _BPS
        return Fill(
            filled_at=bar.timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            fee=fee,
        )
