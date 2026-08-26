"""Tests for the Solana AMM round-trip cost model.

The properties asserted here are the ones the whole meme program leans on:
flat fees dominate small accounts, impact dominates thin pools, and there is a
band of position sizes between the two where trading is possible at all.
"""

from __future__ import annotations

import math

import pytest

from martex_quant.meme.economics import (
    CostModel,
    evaluate_trade,
    max_viable_notional,
    min_viable_notional,
)


def test_price_impact_scales_with_size_over_reserve() -> None:
    model = CostModel()
    # Constant-product: impact ~= 2 * notional / total reserve.
    assert model.price_impact(1_000.0, 100_000.0) == pytest.approx(0.02)
    assert model.price_impact(2_000.0, 100_000.0) == pytest.approx(0.04)


def test_price_impact_is_capped_and_handles_empty_pool() -> None:
    model = CostModel()
    assert model.price_impact(1_000_000.0, 1_000.0) == 1.0
    assert model.price_impact(100.0, 0.0) == 1.0


def test_flat_fee_dominates_small_positions() -> None:
    """The core economic claim: the same pool is untradable small, fine large."""
    model = CostModel()
    deep_pool = 500_000.0
    small = model.round_trip_cost_frac(20.0, deep_pool)
    large = model.round_trip_cost_frac(5_000.0, deep_pool)
    assert small > large
    # A $20 ticket pays over 4% in flat fees alone (2 legs x $0.40, plus failures).
    assert small > 0.04


def test_impact_dominates_large_positions_in_thin_pools() -> None:
    model = CostModel()
    thin_pool = 8_000.0
    assert model.round_trip_cost_frac(50.0, thin_pool) < model.round_trip_cost_frac(
        4_000.0, thin_pool
    )


def test_breakeven_equals_round_trip_friction() -> None:
    model = CostModel()
    assert model.breakeven_gross_return(100.0, 50_000.0) == pytest.approx(
        model.round_trip_cost_frac(100.0, 50_000.0)
    )


def test_failed_attempts_add_fee_payments() -> None:
    """A 5% failure rate must cost more than a 0% one, all else equal."""
    reliable = CostModel(failure_rate=0.0)
    flaky = CostModel(failure_rate=0.20)
    assert flaky.round_trip_cost_usd(100.0, 50_000.0) > reliable.round_trip_cost_usd(
        100.0, 50_000.0
    )


def test_evaluate_trade_rejects_tiny_position_and_names_the_reason() -> None:
    verdict = evaluate_trade(5.0, 500_000.0)
    assert not verdict.viable
    assert verdict.fee_share_of_cost > 0.5
    assert "too small" in verdict.reason


def test_evaluate_trade_rejects_oversized_position_in_thin_pool() -> None:
    verdict = evaluate_trade(20_000.0, 30_000.0)
    assert not verdict.viable
    assert "too thin" in verdict.reason


def test_evaluate_trade_accepts_sensible_position() -> None:
    verdict = evaluate_trade(200.0, 250_000.0)
    assert verdict.viable
    assert 0.0 < verdict.round_trip_frac < 0.15


def test_evaluate_trade_rejects_non_positive_notional() -> None:
    verdict = evaluate_trade(0.0, 100_000.0)
    assert not verdict.viable
    assert math.isinf(verdict.round_trip_frac)


def test_viable_band_brackets_accepted_sizes() -> None:
    """Sizes inside [min, max] must pass; sizes outside must not."""
    reserve = 200_000.0
    low = min_viable_notional(reserve)
    high = max_viable_notional(reserve)
    assert 0.0 < low < high
    assert evaluate_trade(low * 1.5, reserve).viable
    assert evaluate_trade(high * 0.9, reserve).viable
    assert not evaluate_trade(low * 0.2, reserve).viable
    assert not evaluate_trade(high * 3.0, reserve).viable


def test_thin_pool_can_have_no_viable_band_at_all() -> None:
    """Below some depth, flat fees and impact overlap and nothing works."""
    assert max_viable_notional(200.0) == 0.0
    assert math.isinf(min_viable_notional(200.0))


def test_max_viable_notional_grows_with_depth() -> None:
    assert max_viable_notional(1_000_000.0) > max_viable_notional(100_000.0)
