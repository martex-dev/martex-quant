"""Donchian channel breakout. Hypothesis: docs/hypotheses/07-donchian.md."""

from __future__ import annotations

from martex_quant.backtesting.history import History
from martex_quant.strategies.base import Strategy


class DonchianBreakout(Strategy):
    """Long when close breaks above the prior ``channel``-bar high; exit when
    close falls below the prior ``channel//2``-bar low. Classic turtle-style
    trend entry with a trailing channel exit — one parameter.

    Holds internal in/out state (hysteresis); the engine's warmup phase just
    means the strategy starts flat when it goes live, which is correct.
    """

    def __init__(self, channel: int) -> None:
        if channel < 4:
            raise ValueError("channel must be >= 4")
        self.channel = channel
        self.exit_channel = max(2, channel // 2)
        self._long = False

    def on_bar(self, history: History) -> float:
        if len(history) < self.channel + 1:
            return 0.0
        close = history.current.close
        if self._long:
            prior_lows = history.window(self.exit_channel + 1)[:-1]
            self._long = close > min(bar.low for bar in prior_lows)
        else:
            prior_highs = history.window(self.channel + 1)[:-1]
            self._long = close > max(bar.high for bar in prior_highs)
        return 1.0 if self._long else 0.0
