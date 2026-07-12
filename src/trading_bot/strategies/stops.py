"""Chandelier-stop overlays on the deployed specs. Spec: docs/hypotheses/42-stop-overlay.md.

Stop state per symbol (both constants taken as-tested from H40, zero free
parameters): FIRES when close <= trailing-30d-close-high - 2 x ATR14;
CLEARS when close makes a new trailing 30d close-high. While stopped the
symbol is ineligible to hold.
"""

from __future__ import annotations

from statistics import mean

from trading_bot.backtesting.history import History
from trading_bot.strategies.base import Strategy
from trading_bot.strategies.rotation import VolTargetRotation
from trading_bot.strategies.vol_target import VolTargetMomentum

HIGH_WINDOW = 30
ATR_WINDOW = 14
ATR_MULT = 2.0
_MIN_BARS = max(HIGH_WINDOW, ATR_WINDOW + 1)


def update_stop(history: History, stopped: bool) -> bool:
    """Advance the stop latch one bar. With too little history: not stopped."""
    if len(history) < _MIN_BARS:
        return False
    closes = history.closes(HIGH_WINDOW)
    hi = max(closes)
    close = history.current.close
    if stopped:
        return close < hi  # a new 30d close-high clears the latch
    bars = history.window(ATR_WINDOW + 1)
    trs = [
        max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        for i in range(1, len(bars))
    ]
    return close <= hi - ATR_MULT * mean(trs)


class StopVolTargetMomentum(Strategy):
    """42a: VolTargetMomentum with the chandelier latch; flat while stopped."""

    def __init__(
        self,
        lookback: int,
        target_vol_annual: float = 0.30,
        vol_window: int = 30,
    ) -> None:
        self._base = VolTargetMomentum(lookback, target_vol_annual, vol_window)
        self.lookback = lookback
        self._stopped = False

    def warmup(self) -> int:
        return max(self._base.warmup(), _MIN_BARS)

    def on_bar(self, history: History) -> float:
        self._stopped = update_stop(history, self._stopped)
        if self._stopped:
            return 0.0
        return self._base.on_bar(history)


class StopVolTargetRotation(VolTargetRotation):
    """42b: champion rotation, with stopped symbols excluded from the
    ranking pool at selection time."""

    def __init__(
        self,
        lookback: int,
        top_k: int = 2,
        target_vol_annual: float = 0.30,
        vol_window: int = 30,
    ) -> None:
        super().__init__(lookback, top_k, target_vol_annual, vol_window)
        self._stopped: dict[str, bool] = {}

    @property
    def stopped_symbols(self) -> list[str]:
        return sorted(s for s, stopped in self._stopped.items() if stopped)

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        eligible: dict[str, History] = {}
        for symbol, history in histories.items():
            self._stopped[symbol] = update_stop(history, self._stopped.get(symbol, False))
            if not self._stopped[symbol]:
                eligible[symbol] = history
        if not eligible:
            return {}
        return super().target_weights(eligible)
