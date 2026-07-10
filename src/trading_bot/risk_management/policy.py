"""Risk policy interface and the passthrough implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class RiskPolicy(ABC):
    @abstractmethod
    def adjust(
        self,
        target_exposure: float,
        equity: float,
        initial_equity: float,
        timestamp: datetime,
    ) -> float:
        """Return the exposure actually allowed (may shrink or zero the target).

        This is a gate, not a suggestion: the engine calls it on every bar
        and uses only its return value. Policies are stateful (drawdown
        peaks, day boundaries, kill latches) — one instance per backtest.
        """


class PassthroughPolicy(RiskPolicy):
    """No adjustment beyond clamping to [-1, +1]."""

    def adjust(
        self,
        target_exposure: float,
        equity: float,
        initial_equity: float,
        timestamp: datetime,
    ) -> float:
        return max(-1.0, min(1.0, target_exposure))
