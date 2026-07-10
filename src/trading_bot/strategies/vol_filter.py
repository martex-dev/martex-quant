"""Volatility-regime-filtered momentum.

Hypothesis: docs/hypotheses/03-vol-regime-filter.md. The vol windows are
FIXED (not tuned) to keep the trial count at the momentum grid size only.
"""

from __future__ import annotations

from statistics import stdev

from trading_bot.backtesting.history import History
from trading_bot.strategies.base import Strategy


class VolFilteredMomentum(Strategy):
    """TSMOM, allowed to be long only in a calm-volatility regime.

    Regime gate: realized vol over the short window is below realized vol
    over the long window (calm = recent vol under its own longer baseline).
    """

    def __init__(self, lookback: int, vol_short: int = 30, vol_long: int = 90) -> None:
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        if not 1 < vol_short < vol_long:
            raise ValueError("need 1 < vol_short < vol_long")
        self.lookback = lookback
        self.vol_short = vol_short
        self.vol_long = vol_long

    def warmup(self) -> int:
        return max(self.lookback, self.vol_long) + 1

    def on_bar(self, history: History) -> float:
        if len(history) < self.warmup():
            return 0.0
        if history.current.close <= history[-1 - self.lookback].close:
            return 0.0  # no momentum, no position
        closes = history.closes(self.vol_long + 1)
        returns = [closes[i + 1] / closes[i] - 1.0 for i in range(len(closes) - 1)]
        calm = stdev(returns[-self.vol_short :]) < stdev(returns)
        return 1.0 if calm else 0.0
