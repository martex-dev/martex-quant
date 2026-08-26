"""Prop-firm Monte Carlo tests: deterministic rule checks, reproducibility."""

import pytest

from martex_quant.risk_management.prop_sim import (
    PropFirmRules,
    simulate_evaluation,
    wilson_interval,
)

RULES = PropFirmRules(
    name="TEST-50k",
    account_size=50_000.0,
    profit_target_pct=0.06,
    trailing_dd_pct=0.04,
    daily_loss_pct=0.02,
    max_days=365,
    evaluation_fee=170.0,
)


def test_steady_gains_always_pass() -> None:
    result = simulate_evaluation([0.005] * 100, RULES, n_paths=200)
    assert result.pass_rate == 1.0
    # +0.5%/day compounding reaches +6% on day 12
    assert result.median_days_to_pass == 12


def test_steady_losses_always_bust_on_trailing_dd() -> None:
    result = simulate_evaluation([-0.005] * 100, RULES, n_paths=200)
    assert result.fail_rate == 1.0
    assert result.pass_rate == 0.0


def test_daily_loss_limit_busts_before_trailing() -> None:
    # One -3% day violates the 2% daily limit even though trailing (4%) holds.
    result = simulate_evaluation([-0.03] * 100, RULES, n_paths=100)
    assert result.fail_rate == 1.0


def test_flat_returns_time_out() -> None:
    result = simulate_evaluation([0.0] * 100, RULES, n_paths=100, horizon_days=50)
    assert result.timeout_rate == 1.0


def test_seed_reproducibility() -> None:
    returns = [0.01, -0.008, 0.004, -0.002, 0.006, -0.01, 0.003, 0.007, -0.004, 0.002] * 30
    a = simulate_evaluation(returns, RULES, n_paths=500, seed=42)
    b = simulate_evaluation(returns, RULES, n_paths=500, seed=42)
    c = simulate_evaluation(returns, RULES, n_paths=500, seed=43)
    assert a.pass_rate == b.pass_rate
    assert (a.pass_rate, a.fail_rate) != (c.pass_rate, c.fail_rate) or a.pass_rate in (0.0, 1.0)


def test_risk_scale_shrinks_both_tails() -> None:
    returns = [0.02, -0.015, 0.01, -0.01, 0.015, -0.02, 0.01, 0.005, -0.005, 0.01] * 30
    full = simulate_evaluation(returns, RULES, risk_scale=1.0, n_paths=2000, horizon_days=100)
    tiny = simulate_evaluation(returns, RULES, risk_scale=0.1, n_paths=2000, horizon_days=100)
    # At 10% scale the daily/trailing limits are nearly untouchable but the
    # target is also nearly unreachable within a short horizon.
    assert tiny.fail_rate < full.fail_rate
    assert tiny.pass_rate + tiny.timeout_rate > full.pass_rate + full.timeout_rate
    assert tiny.timeout_rate > 0.5  # too slow to reach +6% in 100 days at 0.1x


def test_expected_value_math() -> None:
    result = simulate_evaluation([0.005] * 100, RULES, n_paths=100)
    assert result.expected_value(funded_account_value=5000.0) == pytest.approx(1.0 * 5000.0 - 170.0)


def test_wilson_interval_sane() -> None:
    low, high = wilson_interval(50, 100)
    assert low < 0.5 < high
    assert wilson_interval(0, 0) == (0.0, 1.0)
    low0, _ = wilson_interval(0, 100)
    assert low0 == 0.0


def test_input_validation() -> None:
    with pytest.raises(ValueError):
        simulate_evaluation([0.01] * 5, RULES, block_size=10)
    with pytest.raises(ValueError):
        simulate_evaluation([0.01] * 100, RULES, risk_scale=0.0)
