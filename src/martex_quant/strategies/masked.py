"""Restrict any multi-asset strategy to a time-varying universe.

Spec: docs/hypotheses/71-point-in-time-universe.md Section 4.3.

The engine takes one fixed set of frames for a whole run, but a
point-in-time universe changes underneath it. Rather than teach the
engine about universes, this wrapper hands the inner strategy only the
symbols that were selectable on the day being decided. Everything the
inner strategy cannot see, it cannot hold.

Statefulness is deliberate here: `StopVolTargetRotation` tracks a stop
per symbol, and wrapping it means stops advance only for symbols inside
the universe. That is the honest behaviour -- an operator does not
maintain a trailing stop on a coin they are not watching.
"""

from __future__ import annotations

from martex_quant.backtesting.history import History
from martex_quant.backtesting.multi import MultiAssetStrategy
from martex_quant.features.universe import UniverseSchedule


class UniverseMasked(MultiAssetStrategy):
    """Delegate to ``inner``, but only over the day's selectable symbols."""

    def __init__(self, inner: MultiAssetStrategy, schedule: UniverseSchedule) -> None:
        self.inner = inner
        self.schedule = schedule

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        if not histories:
            return {}
        today = max(h.current.timestamp for h in histories.values()).date()
        allowed = self.schedule.for_date(today)
        if not allowed:
            return {}
        visible = {s: h for s, h in histories.items() if s in allowed}
        if not visible:
            return {}
        return self.inner.target_weights(visible)
