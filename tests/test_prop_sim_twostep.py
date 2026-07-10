"""Tests for static max loss and two-step evaluation simulation."""

import pytest

from trading_bot.risk_management.prop_sim import (
    PropFirmRules,
    simulate_evaluation,
    simulate_two_step,
)

STATIC_RULES = PropFirmRules(
    name="static-5k",
    account_size=5_000.0,
    profit_target_pct=0.10,
    trailing_dd_pct=None,
    daily_loss_pct=0.03,
    max_days=None,
    evaluation_fee=65.0,
    static_max_loss_pct=0.06,  # $300 on 5k
)


def test_rules_require_some_loss_limit() -> None:
    with pytest.raises(ValueError, match="at least one"):
        PropFirmRules("bad", 5000.0, 0.10, None, None, None, 65.0)


def test_static_floor_busts_only_below_initial_floor() -> None:
    # +2% then -2.5% alternating: dips never take equity below 5000*(0.94),
    # daily losses stay under 3%; slow grind up passes eventually.
    returns = [0.02, -0.0075] * 200
    result = simulate_evaluation(returns, STATIC_RULES, n_paths=200, horizon_days=400)
    assert result.pass_rate == 1.0


def test_static_floor_allows_deep_trailing_drawdown() -> None:
    """A path that runs up +8% then gives back 7% would bust ANY 4% trailing
    rule, but a static $300 floor survives it (equity stays above 4700)."""
    returns = [0.008] * 10 + [-0.0073] * 10 + [0.008] * 30
    static = simulate_evaluation(returns, STATIC_RULES, n_paths=100, block_size=5)
    trailing = simulate_evaluation(
        returns,
        PropFirmRules("trail-5k", 5_000.0, 0.10, 0.04, 0.03, None, 65.0),
        n_paths=100,
        block_size=5,
    )
    assert static.fail_rate < trailing.fail_rate


def test_two_step_pass_requires_both_stages() -> None:
    stage1 = PropFirmRules("s1", 5_000.0, 0.10, None, 0.05, None, 45.0, static_max_loss_pct=0.10)
    stage2 = PropFirmRules("s2", 5_000.0, 0.05, None, 0.05, None, 0.0, static_max_loss_pct=0.10)
    steady = [0.005] * 100
    result = simulate_two_step(steady, stage1, stage2, n_paths=200)
    assert result.pass_rate == 1.0
    # ~+10% needs 20 days at 0.5%/day compounding; +5% needs 10 more.
    assert result.median_days_to_pass == 30


def test_two_step_harder_than_single_step_on_noisy_returns() -> None:
    returns = [0.02, -0.018, 0.015, -0.01, 0.012, -0.02, 0.01, 0.008, -0.006, 0.004] * 30
    stage1 = PropFirmRules("s1", 5_000.0, 0.10, None, 0.05, None, 45.0, static_max_loss_pct=0.10)
    stage2 = PropFirmRules("s2", 5_000.0, 0.05, None, 0.05, None, 0.0, static_max_loss_pct=0.10)
    single = simulate_evaluation(returns, stage1, n_paths=2000)
    double = simulate_two_step(returns, stage1, stage2, n_paths=2000)
    assert double.pass_rate <= single.pass_rate
    assert single.median_days_to_pass is not None and double.median_days_to_pass is not None
    assert double.median_days_to_pass > single.median_days_to_pass  # stage 2 costs time


def test_two_step_reproducible() -> None:
    returns = [0.01, -0.008, 0.006, -0.004] * 50
    stage1 = PropFirmRules("s1", 5_000.0, 0.10, None, 0.05, None, 45.0, static_max_loss_pct=0.10)
    stage2 = PropFirmRules("s2", 5_000.0, 0.05, None, 0.05, None, 0.0, static_max_loss_pct=0.10)
    a = simulate_two_step(returns, stage1, stage2, n_paths=500, seed=11)
    b = simulate_two_step(returns, stage1, stage2, n_paths=500, seed=11)
    assert a.pass_rate == b.pass_rate and a.fail_rate == b.fail_rate
