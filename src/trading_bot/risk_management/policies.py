"""Concrete risk policies. Mechanical and dumb by design: a risk rule you
can argue with mid-drawdown is not a risk rule.

Every policy can only shrink exposure toward zero, never amplify it.
"""

from __future__ import annotations

from datetime import datetime

from trading_bot.risk_management.policy import RiskPolicy


def _clamp(exposure: float) -> float:
    return max(-1.0, min(1.0, exposure))


class MaxExposurePolicy(RiskPolicy):
    """Hard cap on absolute exposure."""

    def __init__(self, max_exposure: float) -> None:
        if not 0.0 < max_exposure <= 1.0:
            raise ValueError("max_exposure must be in (0, 1]")
        self.max_exposure = max_exposure

    def adjust(
        self, target_exposure: float, equity: float, initial_equity: float, timestamp: datetime
    ) -> float:
        target = _clamp(target_exposure)
        return max(-self.max_exposure, min(self.max_exposure, target))


class DrawdownGuardPolicy(RiskPolicy):
    """Shrinks exposure linearly as drawdown deepens; kills at the hard limit.

    - drawdown <= soft_dd: full target allowed
    - between soft and hard: linear scale toward zero
    - >= hard_dd: exposure zero and the kill switch LATCHES — no automatic
      re-entry on recovery, ever. Un-latching is a human decision made
      outside the system, after understanding what went wrong.
    """

    def __init__(self, soft_dd: float, hard_dd: float) -> None:
        if not 0.0 < soft_dd < hard_dd < 1.0:
            raise ValueError("need 0 < soft_dd < hard_dd < 1")
        self.soft_dd = soft_dd
        self.hard_dd = hard_dd
        self._peak = float("-inf")
        self._killed = False

    @property
    def killed(self) -> bool:
        return self._killed

    def adjust(
        self, target_exposure: float, equity: float, initial_equity: float, timestamp: datetime
    ) -> float:
        self._peak = max(self._peak, equity)
        drawdown = 1.0 - equity / self._peak if self._peak > 0 else 0.0
        # Small epsilon so a breach of exactly hard_dd trips the kill switch
        # despite float rounding (1 - 900/1000 is 0.0999... in binary).
        if self._killed or drawdown >= self.hard_dd - 1e-12:
            self._killed = True
            return 0.0
        target = _clamp(target_exposure)
        if drawdown <= self.soft_dd:
            return target
        scale = (self.hard_dd - drawdown) / (self.hard_dd - self.soft_dd)
        return target * scale


class DailyLossPolicy(RiskPolicy):
    """Flat for the remainder of the UTC day once the day's loss (from that
    day's starting equity) exceeds the limit. Re-arms at the next day."""

    def __init__(self, max_daily_loss: float) -> None:
        if not 0.0 < max_daily_loss < 1.0:
            raise ValueError("max_daily_loss must be in (0, 1)")
        self.max_daily_loss = max_daily_loss
        self._day: object = None
        self._day_start_equity = 0.0
        self._halted = False

    def adjust(
        self, target_exposure: float, equity: float, initial_equity: float, timestamp: datetime
    ) -> float:
        day = timestamp.date()
        if day != self._day:
            self._day = day
            self._day_start_equity = equity
            self._halted = False
        if equity <= self._day_start_equity * (1.0 - self.max_daily_loss):
            self._halted = True
        return 0.0 if self._halted else _clamp(target_exposure)


class CompositePolicy(RiskPolicy):
    """Applies policies in sequence; each sees the previous one's output.
    Since every policy only shrinks, order affects intermediate values but
    the result is always <= the tightest individual constraint."""

    def __init__(self, policies: list[RiskPolicy]) -> None:
        if not policies:
            raise ValueError("need at least one policy")
        self.policies = policies

    def adjust(
        self, target_exposure: float, equity: float, initial_equity: float, timestamp: datetime
    ) -> float:
        exposure = target_exposure
        for policy in self.policies:
            exposure = policy.adjust(exposure, equity, initial_equity, timestamp)
        return exposure


def mode1_policy() -> CompositePolicy:
    """Funded-account profile: capital preservation first.

    Half sizing, exposure shrinking from 5% drawdown, killed at 10%,
    flat after a 2% daily loss.
    """
    return CompositePolicy(
        [
            MaxExposurePolicy(0.5),
            DrawdownGuardPolicy(soft_dd=0.05, hard_dd=0.10),
            DailyLossPolicy(max_daily_loss=0.02),
        ]
    )


def mode2_policy() -> CompositePolicy:
    """Experimental profile: full sizing, wide guard. The kill switch at 40%
    exists because 'experimental' does not mean 'unlimited'."""
    return CompositePolicy(
        [
            MaxExposurePolicy(1.0),
            DrawdownGuardPolicy(soft_dd=0.25, hard_dd=0.40),
        ]
    )
