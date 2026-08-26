"""The H58 walk-forward harness is the only reason H58's numbers are
admissible, so it is tested on its safety properties rather than its outputs.

The decisive pair is the null control and the positive control. A harness that
reports skill on pure noise is leaking; a harness that cannot find a signal
that is genuinely there would make every kill meaningless. Both must hold.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from martex_quant.research.ensemble import (
    LeakageError,
    assert_features_are_causal,
    leak_alarm,
    purged_windows,
    run_walk_forward,
)

TRAIN, TEST, PURGE = 30, 10, 3


def _panel(*, informative: bool, seed: int, days: int = 220, symbols: int = 6) -> pl.DataFrame:
    """Synthetic panel. ``informative`` decides whether ``x`` causally drives
    the forward outcome or is unrelated to it."""
    rng = np.random.default_rng(seed)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = days * symbols
    x = rng.normal(size=rows)
    noise = rng.normal(size=rows)
    outcome = (0.9 * x + 0.4 * noise) if informative else noise
    return pl.DataFrame(
        {
            "day": [start + timedelta(days=d) for d in range(days) for _ in range(symbols)],
            "symbol": [f"S{s}" for _ in range(days) for s in range(symbols)],
            "x": x,
            "z": rng.normal(size=rows),
            "fwd_outcome": outcome,
            "target": (outcome > 0).astype(np.int8),
        }
    )


def _run(frame: pl.DataFrame, features: list[str]):  # noqa: ANN202
    return run_walk_forward(
        frame,
        name="t",
        features=features,
        target="target",
        outcome="fwd_outcome",
        train=TRAIN,
        test=TEST,
        purge=PURGE,
        penalty="none",
    )


class TestPurgedWindows:
    def test_gap_is_exactly_the_purge(self) -> None:
        for w in purged_windows(200, train=TRAIN, test=TEST, purge=PURGE):
            assert w.test_start == w.train_end + PURGE

    def test_no_window_runs_past_the_data(self) -> None:
        assert all(w.test_end <= 200 for w in purged_windows(200, train=TRAIN, test=TEST, purge=3))

    def test_test_slices_do_not_overlap(self) -> None:
        windows = purged_windows(200, train=TRAIN, test=TEST, purge=PURGE)
        for earlier, later in zip(windows[:-1], windows[1:], strict=True):
            assert later.test_start >= earlier.test_end

    def test_too_little_data_yields_nothing_rather_than_a_short_window(self) -> None:
        assert purged_windows(20, train=TRAIN, test=TEST, purge=PURGE) == []

    def test_rejects_nonsense_spans(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            purged_windows(200, train=0, test=TEST, purge=PURGE)


class TestLeakGuards:
    def test_forward_named_features_are_refused(self) -> None:
        with pytest.raises(LeakageError, match="forward-derived"):
            assert_features_are_causal(["r30", "fwd7"])

    def test_causal_features_pass(self) -> None:
        assert_features_are_causal(["r30", "vol30"])  # must not raise

    def test_the_outcome_as_its_own_predictor_is_flagged(self) -> None:
        frame = _panel(informative=True, seed=1)
        assert any("IS the outcome" in f for f in leak_alarm(frame, ["fwd_outcome"], "fwd_outcome"))

    def test_alarm_is_sensitive_to_a_near_copy(self) -> None:
        """The failure the first H58 run caught: an alarm that cannot fire on a
        near-perfect leak is not a guard."""
        frame = _panel(informative=True, seed=2).with_columns(
            sneaky=pl.col("fwd_outcome") * 1.01 + 0.001
        )
        assert leak_alarm(frame, ["sneaky"], "fwd_outcome")

    def test_alarm_is_quiet_on_an_honest_feature(self) -> None:
        assert leak_alarm(_panel(informative=True, seed=3), ["z"], "fwd_outcome") == []

    def test_the_runner_itself_refuses_a_forward_feature(self) -> None:
        with pytest.raises(LeakageError):
            _run(_panel(informative=True, seed=4), ["x", "fwd_outcome"])


class TestControls:
    def test_null_control_finds_no_skill_in_noise(self) -> None:
        """Features unrelated to the outcome must score near chance. If this
        drifts high, the harness is seeing the future and every result from it
        is void."""
        run = _run(_panel(informative=False, seed=11), ["x", "z"])
        assert run.n_windows > 5
        assert abs(run.accuracy - 0.5) < 0.05

    def test_positive_control_recovers_a_real_signal(self) -> None:
        """A harness that cannot detect a planted signal makes every kill
        uninformative — the kill would just be the harness being blind."""
        run = _run(_panel(informative=True, seed=12), ["x", "z"])
        assert run.accuracy > 0.75

    def test_out_of_sample_rows_never_come_from_the_purge_gap(self) -> None:
        frame = _panel(informative=True, seed=13)
        run = _run(frame, ["x"])
        days = frame["day"].unique().sort()
        allowed = {
            d
            for w in purged_windows(len(days), train=TRAIN, test=TEST, purge=PURGE)
            for d in days[w.test_start : w.test_end]
        }
        assert set(run.predictions["day"].unique()) <= allowed


class TestEqualWeightBaseline:
    def test_equal_weighting_fits_nothing(self) -> None:
        run = run_walk_forward(
            _panel(informative=True, seed=21),
            name="B",
            features=["x", "z"],
            target="target",
            outcome="fwd_outcome",
            train=TRAIN,
            test=TEST,
            purge=PURGE,
            penalty="none",
            equal_weight=True,
        )
        assert all(set(w.values()) == {1.0} for w in run.weights)

    def test_stability_reports_the_modal_sign_share(self) -> None:
        run = _run(_panel(informative=True, seed=22), ["x", "z"])
        # x genuinely drives the outcome, so its sign should be near-unanimous.
        assert run.sign_stability()["x"] > 0.9
        assert run.mean_weights()["x"] > 0
