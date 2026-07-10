"""Benchmark and known-answer strategies.

These exist to validate the engine, not to make money: their trades are
hand-computable, so the engine's output can be checked exactly.
"""

from __future__ import annotations

from trading_bot.backtesting.history import History
from trading_bot.strategies.base import Strategy


class BuyAndHold(Strategy):
    """Fully long from the first bar onward. The canonical benchmark."""

    def on_bar(self, history: History) -> float:
        return 1.0


class Flat(Strategy):
    """Never in the market. Final equity must equal initial cash exactly."""

    def on_bar(self, history: History) -> float:
        return 0.0


class SmaCross(Strategy):
    """Long when the fast SMA is above the slow SMA, flat otherwise.

    A teaching/validation strategy — NOT a candidate edge (see project rules
    on indicator-only strategies).
    """

    def __init__(self, fast: int, slow: int) -> None:
        if not 0 < fast < slow:
            raise ValueError("need 0 < fast < slow")
        self.fast = fast
        self.slow = slow

    def on_bar(self, history: History) -> float:
        if len(history) < self.slow:
            return 0.0
        closes = history.closes(self.slow)
        sma_slow = sum(closes) / self.slow
        sma_fast = sum(closes[-self.fast :]) / self.fast
        return 1.0 if sma_fast > sma_slow else 0.0
