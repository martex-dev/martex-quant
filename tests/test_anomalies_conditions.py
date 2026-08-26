"""Stages 9 and 10: anomaly leads, and strategy x market-state guards.

The tests that matter here are the negative ones — that an anomaly cannot
become a finding, that days are never counted as episodes, and that the
guarded drawdown window refuses to be examined without pre-registration.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from martex_quant.research import anomalies as an
from martex_quant.research.strategy_conditions import (
    GUARDED_WINDOW,
    MATURITY_CEILING,
    PreRegistrationRequired,
    conditional_performance,
    find_episodes,
    guard_drawdown_window,
    performance_matrix,
    render,
)

START = datetime(2021, 1, 1, tzinfo=UTC)


def _panel(n_days: int = 400, n_symbols: int = 8, *, spike_day: int | None = None) -> pl.DataFrame:
    rng = random.Random(7)
    rows = []
    for d in range(n_days):
        for s in range(n_symbols):
            ret = rng.gauss(0.0, 0.02)
            if spike_day is not None and d == spike_day:
                ret = 0.45  # a violent, unmistakable move
            rows.append({"day": START + timedelta(days=d), "symbol": f"S{s}", "ret": ret})
    return pl.DataFrame(rows)


# --- stage 9: anomalies are leads, never findings ------------------------


def test_a_violent_move_is_surfaced_as_a_lead() -> None:
    found = an.detect_volatility_shifts(_panel(spike_day=300), window=90, threshold=4.0)
    assert found
    assert any(a.at == START + timedelta(days=300) for a in found)
    text = found[0].as_lead()
    assert text.startswith("[LEAD]")
    assert "not a finding" in text


def test_quiet_data_yields_no_leads() -> None:
    assert an.scan(_panel(), window=90, threshold=6.0) == []


def test_a_synchronised_move_is_flagged_as_a_correlation_lead() -> None:
    """Everything moving the same way is the signature of a stress episode.

    Needs a WIDE cross-section to be anomalous at all: with only 8 symbols the
    share moving the same way is so coarse that "all of them" sits about 1.7
    robust sd from the norm — genuinely not unusual. That is a property of the
    measure, not a defect, and the reason this test uses 20 symbols.
    """
    panel = _panel(spike_day=250, n_symbols=20)
    found = an.detect_correlation_shifts(panel, window=90, threshold=3.0)
    assert any(a.at == START + timedelta(days=250) for a in found)


def test_there_is_no_way_to_promote_an_anomaly_to_a_finding() -> None:
    """The structural guarantee of this stage. An anomaly can only become a
    finding by being written up as a new pre-registered hypothesis."""
    for forbidden in ("promote", "confirm", "validate", "accept", "to_finding"):
        assert not hasattr(an, forbidden), f"anomalies must not expose {forbidden}()"
    assert not hasattr(an.Anomaly, "verdict")


def test_severity_is_ranked_but_never_called_significance() -> None:
    found = an.scan(_panel(spike_day=300), window=90, threshold=3.0)
    assert found == sorted(found, key=lambda a: a.severity, reverse=True)
    assert "robust sd" in found[0].as_lead()
    assert "p-value" not in found[0].as_lead().lower()
    assert "none is a finding" in an.summarise(found)


# --- stage 10: episodes, not days ----------------------------------------


def _strategy_frame(n_days: int = 60) -> pl.DataFrame:
    rng = random.Random(3)
    return pl.DataFrame(
        {
            "day": [START + timedelta(days=i) for i in range(n_days)],
            "strategy_return": [rng.gauss(0.001, 0.01) for _ in range(n_days)],
            "stressed": [i // 10 % 2 == 0 for i in range(n_days)],
        }
    )


def test_a_long_run_counts_as_one_episode_not_many_days() -> None:
    """The core method. A 26-day drawdown is n=1, not n=26."""
    frame = pl.DataFrame(
        {
            "day": [START + timedelta(days=i) for i in range(30)],
            "strategy_return": [0.001] * 30,
            "stressed": [i < 26 for i in range(30)],
        }
    )
    episodes = find_episodes(frame, pl.col("stressed"), return_column="strategy_return")
    assert len(episodes) == 1
    assert episodes[0].days == 26


def test_separate_runs_are_separate_episodes() -> None:
    episodes = find_episodes(_strategy_frame(), pl.col("stressed"), return_column="strategy_return")
    assert len(episodes) == 3  # days 0-9, 20-29, 40-49
    assert all(e.days == 10 for e in episodes)


def test_output_is_descriptive_and_carries_no_significance() -> None:
    result = conditional_performance(_strategy_frame(), pl.col("stressed"), "stressed regime")
    assert result.episodes == 3
    assert result.too_few_episodes  # 3 < 10
    text = result.describe()
    assert "DESCRIPTIVE ONLY" in text
    assert "too few for inference" in text
    assert not hasattr(result, "p_value")
    assert MATURITY_CEILING == "L1"


def test_the_matrix_header_states_a_filter_is_a_new_strategy() -> None:
    matrix = performance_matrix(
        _strategy_frame(),
        {"stressed": pl.col("stressed"), "calm": ~pl.col("stressed")},
        return_column="strategy_return",
    )
    text = render(matrix)
    assert "NEW STRATEGY" in text
    assert "Nothing below is a finding" in text
    assert len(matrix) == 2


# --- the drawdown guardrail ----------------------------------------------


def test_the_guarded_drawdown_window_refuses_to_be_examined() -> None:
    """PROJECT_STATE's guardrail, enforced in code rather than remembered."""
    start, end = GUARDED_WINDOW
    with pytest.raises(PreRegistrationRequired, match="guarded paper"):
        guard_drawdown_window(start, end)
    # ...and says why, in terms of episodes.
    try:
        guard_drawdown_window(start, end)
    except PreRegistrationRequired as exc:
        assert "one episode, not a sample" in str(exc)


def test_a_pre_registration_reference_unlocks_it() -> None:
    start, end = GUARDED_WINDOW
    guard_drawdown_window(start, end, preregistration="docs/hypotheses/58-drawdown.md")


def test_windows_outside_the_guard_are_unaffected() -> None:
    guard_drawdown_window(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 6, 1, tzinfo=UTC))


def test_conditional_performance_refuses_the_guarded_window_too() -> None:
    guard_start, _ = GUARDED_WINDOW
    frame = pl.DataFrame(
        {
            "day": [guard_start + timedelta(days=i) for i in range(20)],
            "strategy_return": [0.0] * 20,
            "flag": [True] * 20,
        }
    )
    with pytest.raises(PreRegistrationRequired):
        conditional_performance(frame, pl.col("flag"), "anything")
