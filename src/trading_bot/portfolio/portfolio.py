"""Exposure-to-order translation and cash/position accounting.

Orders are generated only when the (risk-adjusted) target exposure CHANGES.
This avoids per-bar rebalancing churn: a strategy holding +1.0 does not
generate a stream of tiny adjustment orders as prices drift.
"""

from __future__ import annotations

from trading_bot.core.events import Bar, Fill, Order, Side


class Portfolio:
    def __init__(self, symbol: str, initial_cash: float, allow_short: bool = False) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.symbol = symbol
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.position = 0.0  # base units; negative = short
        self.allow_short = allow_short
        self._last_target: float | None = None

    def equity(self, price: float) -> float:
        return self.cash + self.position * price

    def target_order(self, target_exposure: float, bar: Bar) -> Order | None:
        """Turn a target exposure into an order sized off equity at this close.

        Returns None when the target is unchanged since the last signal or
        the resulting trade is zero-size.
        """
        target = max(-1.0, min(1.0, target_exposure))
        if not self.allow_short:
            target = max(0.0, target)
        if self._last_target is not None and target == self._last_target:
            return None
        self._last_target = target

        target_units = target * self.equity(bar.close) / bar.close
        delta = target_units - self.position
        if delta == 0.0:
            return None
        return Order(
            created_at=bar.timestamp,
            symbol=self.symbol,
            side=Side.BUY if delta > 0 else Side.SELL,
            quantity=abs(delta),
        )

    def apply_fill(self, fill: Fill) -> None:
        self.cash -= fill.signed_quantity * fill.price + fill.fee
        self.position += fill.signed_quantity
