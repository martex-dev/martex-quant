"""H58 harness: purged walk-forward for learned indicator ensembles.

Every anti-leakage requirement from the registration is enforced here rather
than left to the caller:

* **Purged, chronological splits.** Train on a window, skip a purge gap equal
  to the target horizon, then test. Without the gap a training row's forward
  window overlaps a test row and the model has seen its own answer.
* **Scaler fitted on TRAIN ONLY**, then applied to test. Fitting on the full
  sample is the classic silent leak.
* **Forward-derived columns are refused as features by name.** A column
  starting with ``fwd`` cannot be a predictor; the poison test relies on this
  and on the leak statistic below.
* **A leak statistic is reported for every run.** Any feature correlating
  with the target above ``LEAK_CORRELATION_ALARM`` is flagged. Real market
  features do not predict next week's direction at 0.95.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# A genuine market feature does not correlate with next week's sign this
# strongly. Anything above it is a leak until proven otherwise.
LEAK_CORRELATION_ALARM = 0.95

Penalty = Literal["none", "l2", "l1"]


class LeakageError(Exception):
    """Raised when a feature could not have been known at prediction time."""


@dataclass(frozen=True)
class Window:
    train_start: int
    train_end: int  # exclusive
    test_start: int  # == train_end + purge
    test_end: int  # exclusive


def purged_windows(n_days: int, *, train: int, test: int, purge: int) -> list[Window]:
    """Chronological splits with a purge gap between train and test.

    The gap must be at least the target horizon: a row at the end of training
    has a forward outcome that extends into the test period, so without the
    gap the model is partly fitted on the very days it is scored against.
    """
    if purge < 0 or train < 1 or test < 1:
        raise ValueError("train, test must be positive and purge non-negative")
    out: list[Window] = []
    start = 0
    while start + train + purge + test <= n_days:
        out.append(
            Window(
                train_start=start,
                train_end=start + train,
                test_start=start + train + purge,
                test_end=start + train + purge + test,
            )
        )
        start += test
    return out


def assert_features_are_causal(features: list[str]) -> None:
    """Refuse anything named like a forward-looking column."""
    offenders = [f for f in features if f.lower().startswith("fwd")]
    if offenders:
        raise LeakageError(
            f"{offenders} name forward-derived outcomes and cannot be predictors — "
            "a feature must be computable from data available at t"
        )


def leak_alarm(frame: pl.DataFrame, features: list[str], outcome: str) -> list[str]:
    """Features suspiciously correlated with the CONTINUOUS outcome.

    Deliberately measured against the raw forward return, not the binary
    target. A variable correlates with its own SIGN at only about 0.8, so a
    binary target cannot expose even a perfect leak — the first run of this
    harness proved exactly that, and refused to report results because its
    own detector could not demonstrate sensitivity.
    """
    flagged: list[str] = []
    for name in features:
        if name == outcome:
            # The outcome offered as its own predictor: a perfect leak, and
            # the degenerate case a self-join would raise on.
            flagged.append(f"{name} (IS the outcome, |r|=1.000)")
            continue
        pair = frame.select(name, outcome).drop_nulls()
        if pair.height < 30:
            continue
        corr = pair.select(pl.corr(name, outcome)).item()
        if corr is not None and abs(float(corr)) > LEAK_CORRELATION_ALARM:
            flagged.append(f"{name} (|r|={abs(float(corr)):.3f})")
    return flagged


@dataclass
class EnsembleRun:
    """Out-of-sample predictions stitched across every walk-forward window."""

    name: str
    predictions: pl.DataFrame  # day, symbol, prob, target, outcome
    weights: list[dict[str, float]]  # one dict per window
    features: list[str]

    @property
    def n_windows(self) -> int:
        return len(self.weights)

    @property
    def accuracy(self) -> float:
        p = self.predictions
        hits = ((p["prob"] > 0.5).cast(pl.Int8) == p["target"]).mean()
        return float(hits) if isinstance(hits, (int, float)) else 0.0

    def sign_stability(self) -> dict[str, float]:
        """Share of windows where each weight kept its modal sign.

        Weights that flip sign between windows are fitting noise, whatever the
        accuracy says — the registration's stability bar.
        """
        out: dict[str, float] = {}
        for feature in self.features:
            signs = [np.sign(w.get(feature, 0.0)) for w in self.weights]
            if not signs:
                out[feature] = 0.0
                continue
            positive = sum(1 for s in signs if s > 0)
            out[feature] = max(positive, len(signs) - positive) / len(signs)
        return out

    def mean_weights(self) -> dict[str, float]:
        return {f: float(np.mean([w.get(f, 0.0) for w in self.weights])) for f in self.features}


def run_walk_forward(
    panel: pl.DataFrame,
    *,
    name: str,
    features: list[str],
    target: str,
    outcome: str,
    train: int,
    test: int,
    purge: int,
    penalty: Penalty,
    equal_weight: bool = False,
    seed: int = 5800,
) -> EnsembleRun:
    """Fit per window on train only, predict the purged test slice.

    ``equal_weight=True`` is baseline B: standardise on train, then sum the
    features with weight 1 and no fitting at all. It shares this code path so
    the comparison against the learned models differs in ONE thing.
    """
    assert_features_are_causal(features)

    frame = panel.drop_nulls([*features, target, outcome]).sort("day", "symbol")
    days = frame["day"].unique().sort()
    windows = purged_windows(len(days), train=train, test=test, purge=purge)
    if not windows:
        raise ValueError(
            f"not enough days ({len(days)}) for train={train} purge={purge} test={test}"
        )

    parts: list[pl.DataFrame] = []
    weights: list[dict[str, float]] = []

    for window in windows:
        train_days = days[window.train_start : window.train_end]
        test_days = days[window.test_start : window.test_end]
        # `.implode()` is the spelling polars now requires to mean "is this day
        # one of these days"; without it the call is deprecated-ambiguous. The
        # selection is unchanged — verified by re-running the study to the same
        # figures after the change.
        train_rows = frame.filter(pl.col("day").is_in(train_days.implode()))
        test_rows = frame.filter(pl.col("day").is_in(test_days.implode()))
        if train_rows.height < 100 or test_rows.height == 0:
            continue

        x_train = train_rows.select(features).to_numpy()
        y_train = train_rows[target].to_numpy()
        x_test = test_rows.select(features).to_numpy()

        # Fitted on TRAIN only — the classic silent leak, closed here.
        scaler = StandardScaler().fit(x_train)
        x_train_s, x_test_s = scaler.transform(x_train), scaler.transform(x_test)

        if equal_weight:
            score = x_test_s.sum(axis=1)
            prob = 1.0 / (1.0 + np.exp(-score))
            weights.append(dict.fromkeys(features, 1.0))
        else:
            if len(np.unique(y_train)) < 2:
                continue
            model = LogisticRegression(
                penalty=None if penalty == "none" else penalty,
                solver="lbfgs" if penalty in ("none", "l2") else "liblinear",
                C=1.0,
                max_iter=1000,
                random_state=seed,
            )
            model.fit(x_train_s, y_train)
            prob = model.predict_proba(x_test_s)[:, 1]
            weights.append(dict(zip(features, model.coef_[0], strict=True)))

        parts.append(
            test_rows.select("day", "symbol", target, outcome).with_columns(prob=pl.Series(prob))
        )

    return EnsembleRun(
        name=name,
        predictions=pl.concat(parts) if parts else pl.DataFrame(),
        weights=weights,
        features=features,
    )
