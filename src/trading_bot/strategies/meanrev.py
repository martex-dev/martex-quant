"""Short-horizon mean reversion (Bollinger-style stretch entry).

Hypothesis: docs/hypotheses/04-mean-reversion.md. The window is FIXED; only
the band width is in the trial grid.
"""

from __future__ import annotations

import math

from trading_bot.backtesting.history import History
from trading_bot.strategies.base import Strategy


class BollingerReversion(Strategy):
    """Long while price sits more than ``band_k`` stdevs BELOW its
    ``window``-bar mean; flat once it recovers above that band.

    Deliberately symmetric-free (long only) for spot. Known sharp edge:
    it will hold through crashes until price re-enters the band — the
    hypothesis doc lists this as the expected failure mode.
    """

    def __init__(self, band_k: float, window: int = 168) -> None:
        if band_k <= 0:
            raise ValueError("band_k must be positive")
        if window < 2:
            raise ValueError("window must be >= 2")
        self.band_k = band_k
        self.window = window

    def on_bar(self, history: History) -> float:
        if len(history) < self.window:
            return 0.0
        closes = history.closes(self.window)
        mean = sum(closes) / self.window
        var = sum((c - mean) ** 2 for c in closes) / (self.window - 1)
        lower_band = mean - self.band_k * math.sqrt(var)
        return 1.0 if history.current.close < lower_band else 0.0
