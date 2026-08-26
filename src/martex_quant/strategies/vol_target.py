"""Volatility-targeted momentum. Hypothesis: docs/hypotheses/06-vol-target.md.

Same signal as daily TSMOM; SIZING is inverse to realized volatility so the
position runs at a constant risk budget instead of constant notional. This
is the risk-management insight from hypothesis 03 applied as a dial (size)
rather than a switch (in/out).
"""

from __future__ import annotations

import math
from statistics import stdev

from martex_quant.backtesting.history import History
from martex_quant.strategies.base import Strategy


class VolTargetMomentum(Strategy):
    """Long ``min(1, target_vol / realized_vol)`` when trailing momentum is
    positive, flat otherwise. Vol window and target are FIXED (not in the
    trial grid). Exposure is quantized to 0.05 steps to avoid a stream of
    dust rebalance orders (portfolio orders on every target change).
    """

    def __init__(
        self,
        lookback: int,
        target_vol_annual: float = 0.30,
        vol_window: int = 30,
        periods_per_year: int = 365,
    ) -> None:
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        if not 0.0 < target_vol_annual <= 2.0:
            raise ValueError("target_vol_annual must be in (0, 2]")
        if vol_window < 5:
            raise ValueError("vol_window must be >= 5")
        self.lookback = lookback
        self.target_vol_annual = target_vol_annual
        self.vol_window = vol_window
        self.periods_per_year = periods_per_year

    def warmup(self) -> int:
        return max(self.lookback, self.vol_window) + 1

    def on_bar(self, history: History) -> float:
        if len(history) < self.warmup():
            return 0.0
        if history.current.close <= history[-1 - self.lookback].close:
            return 0.0
        closes = history.closes(self.vol_window + 1)
        returns = [closes[i + 1] / closes[i] - 1.0 for i in range(len(closes) - 1)]
        realized = stdev(returns) * math.sqrt(self.periods_per_year)
        if realized <= 0.0:
            return 1.0  # limit of min(1, target/vol) as vol -> 0 is the cap
        raw = min(1.0, self.target_vol_annual / realized)
        return round(raw * 20.0) / 20.0  # quantize to 0.05 steps
