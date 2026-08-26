"""Time-series momentum. Hypothesis: docs/hypotheses/01-time-series-momentum.md."""

from __future__ import annotations

from martex_quant.backtesting.history import History
from martex_quant.strategies.base import Strategy


class TimeSeriesMomentum(Strategy):
    """Long when the trailing ``lookback``-bar return is positive, else flat.

    One parameter, by design: every extra parameter is another dimension
    of overfitting risk.
    """

    def __init__(self, lookback: int) -> None:
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        self.lookback = lookback

    def on_bar(self, history: History) -> float:
        if len(history) <= self.lookback:
            return 0.0
        past = history[-1 - self.lookback]
        return 1.0 if history.current.close > past.close else 0.0
