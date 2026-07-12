"""Multi-horizon momentum blend. Spec: docs/hypotheses/33-40-timeseries-batch.md
(H33 + follow-up FU-B1).

Instead of walk-forward SELECTING one lookback (H16's follow-up showed the
selector chases noise), the signal AVERAGES horizon agreement: exposure is
proportional to how many of the fixed horizons {30, 90, 180} are positive,
then vol-target sized exactly like hypothesis 06. Zero tunable parameters.
"""

from __future__ import annotations

import math
from statistics import stdev

from trading_bot.backtesting.history import History
from trading_bot.strategies.base import Strategy

HORIZONS = (30, 90, 180)


class BlendMomentum(Strategy):
    """Long ``(k / 3) * min(1, target_vol / realized_vol)`` where ``k`` is the
    number of positive trailing horizons among {30, 90, 180}; flat at k=0.
    Exposure quantized to 0.05 steps like VolTargetMomentum."""

    def __init__(
        self,
        target_vol_annual: float = 0.30,
        vol_window: int = 30,
        periods_per_year: int = 365,
    ) -> None:
        if not 0.0 < target_vol_annual <= 2.0:
            raise ValueError("target_vol_annual must be in (0, 2]")
        if vol_window < 5:
            raise ValueError("vol_window must be >= 5")
        self.target_vol_annual = target_vol_annual
        self.vol_window = vol_window
        self.periods_per_year = periods_per_year

    def warmup(self) -> int:
        return max(max(HORIZONS), self.vol_window) + 1

    def on_bar(self, history: History) -> float:
        if len(history) < self.warmup():
            return 0.0
        close = history.current.close
        score = sum(1 for h in HORIZONS if close > history[-1 - h].close)
        if score == 0:
            return 0.0
        closes = history.closes(self.vol_window + 1)
        returns = [closes[i + 1] / closes[i] - 1.0 for i in range(len(closes) - 1)]
        realized = stdev(returns) * math.sqrt(self.periods_per_year)
        vol_scale = 1.0 if realized <= 0.0 else min(1.0, self.target_vol_annual / realized)
        raw = (score / len(HORIZONS)) * vol_scale
        return round(raw * 20.0) / 20.0
