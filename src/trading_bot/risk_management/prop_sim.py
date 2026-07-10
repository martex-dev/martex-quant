"""Monte Carlo simulation of prop-firm evaluations.

An evaluation is a bet: known fee, estimable pass probability. This module
estimates that probability by block-bootstrapping a strategy's out-of-sample
daily returns against a ruleset, then prices the bet.

Honesty constraints baked in:
- Block bootstrap (not IID) to preserve autocorrelation and vol clustering.
- Trailing drawdown is checked END-OF-DAY (daily data); real intraday
  trailing is stricter, so pass rates here are UPPER bounds.
- Rulesets are GENERIC approximations; real firms' rules must be verified
  before money touches an evaluation (open question in CLAUDE.md).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class PropFirmRules:
    name: str
    account_size: float
    profit_target_pct: float  # pass when equity >= account * (1 + this)
    trailing_dd_pct: float  # fail when equity <= peak * (1 - this), EOD
    daily_loss_pct: float | None  # fail on a single-day loss beyond this
    max_days: int | None  # None = no time limit (horizon still applies)
    evaluation_fee: float


@dataclass(frozen=True)
class EvalResult:
    rules: PropFirmRules
    risk_scale: float
    n_paths: int
    pass_rate: float
    pass_ci_low: float  # 95% Wilson interval
    pass_ci_high: float
    fail_rate: float  # busted a limit
    timeout_rate: float  # neither passed nor busted within the horizon
    median_days_to_pass: int | None

    def expected_value(self, funded_account_value: float) -> float:
        """EV of ONE attempt: P(pass) * assumed funded-account value - fee.

        ``funded_account_value`` is the caller's estimate of what a funded
        account is worth (payouts net of funded-stage failure risk) — the
        most uncertain number in the whole calculation; treat EV curves as
        sensitivity analysis, not point predictions.
        """
        return self.pass_rate * funded_account_value - self.rules.evaluation_fee

    def to_text(self) -> str:
        days = f"{self.median_days_to_pass}" if self.median_days_to_pass is not None else "n/a"
        return (
            f"{self.rules.name} @ scale {self.risk_scale:.2f}: "
            f"pass {self.pass_rate:.1%} (95% CI {self.pass_ci_low:.1%}-{self.pass_ci_high:.1%}), "
            f"bust {self.fail_rate:.1%}, timeout {self.timeout_rate:.1%}, "
            f"median days to pass: {days}"
        )


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1.0 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0.0, center - half), min(1.0, center + half))


def simulate_evaluation(
    daily_returns: list[float],
    rules: PropFirmRules,
    risk_scale: float = 1.0,
    n_paths: int = 10_000,
    block_size: int = 10,
    horizon_days: int = 365,
    seed: int = 7,
) -> EvalResult:
    """Block-bootstrap ``daily_returns`` against a ruleset.

    ``risk_scale`` scales each daily return (fraction of the account run at
    the strategy's notional). Fees on fills are already inside the returns;
    the evaluation fee is priced in expected_value().
    """
    if len(daily_returns) < block_size * 2:
        raise ValueError("need at least two blocks of return history")
    if risk_scale <= 0:
        raise ValueError("risk_scale must be positive")
    rng = random.Random(seed)
    n_days = min(horizon_days, rules.max_days) if rules.max_days else horizon_days
    target = rules.account_size * (1.0 + rules.profit_target_pct)
    max_block_start = len(daily_returns) - block_size

    passes = 0
    busts = 0
    days_to_pass: list[int] = []

    for _ in range(n_paths):
        equity = rules.account_size
        peak = equity
        day = 0
        outcome = "timeout"
        while day < n_days:
            start = rng.randint(0, max_block_start)
            for r in daily_returns[start : start + block_size]:
                day += 1
                prev = equity
                equity *= 1.0 + r * risk_scale
                peak = max(peak, equity)
                if rules.daily_loss_pct is not None and equity <= prev * (
                    1.0 - rules.daily_loss_pct
                ):
                    outcome = "bust"
                    break
                if equity <= peak * (1.0 - rules.trailing_dd_pct):
                    outcome = "bust"
                    break
                if equity >= target:
                    outcome = "pass"
                    break
                if day >= n_days:
                    break
            if outcome != "timeout":
                break
        if outcome == "pass":
            passes += 1
            days_to_pass.append(day)
        elif outcome == "bust":
            busts += 1

    ci_low, ci_high = wilson_interval(passes, n_paths)
    days_to_pass.sort()
    return EvalResult(
        rules=rules,
        risk_scale=risk_scale,
        n_paths=n_paths,
        pass_rate=passes / n_paths,
        pass_ci_low=ci_low,
        pass_ci_high=ci_high,
        fail_rate=busts / n_paths,
        timeout_rate=(n_paths - passes - busts) / n_paths,
        median_days_to_pass=days_to_pass[len(days_to_pass) // 2] if days_to_pass else None,
    )
