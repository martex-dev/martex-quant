"""Risk policy interface and the Phase 2 passthrough implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RiskPolicy(ABC):
    @abstractmethod
    def adjust(self, target_exposure: float, equity: float, initial_equity: float) -> float:
        """Return the exposure actually allowed (may shrink or zero the target).

        This is a gate, not a suggestion: the engine calls it on every bar
        and uses only its return value.
        """


class PassthroughPolicy(RiskPolicy):
    """No adjustment beyond clamping to [-1, +1]. Placeholder until Phase 4."""

    def adjust(self, target_exposure: float, equity: float, initial_equity: float) -> float:
        return max(-1.0, min(1.0, target_exposure))
