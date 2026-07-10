"""Strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trading_bot.backtesting.history import History


class Strategy(ABC):
    @abstractmethod
    def on_bar(self, history: History) -> float:
        """Called once per closed bar. Return target exposure in [-1, +1].

        +1 = fully long, 0 = flat, -1 = fully short. The portfolio layer
        translates exposure into orders; the risk layer may shrink or veto.
        """
