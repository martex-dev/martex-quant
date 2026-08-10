"""Tests for the TSLA CNN study.

The important tests here are the leakage tests. A direction model that
accidentally sees the future produces a beautiful, entirely fake result,
and nothing downstream would catch it — so causality and split hygiene are
asserted directly rather than assumed.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from trading_bot.research.tesla.dataset import (
    DOWN,
    NEUTRAL,
    UP,
    Bars,
    build_dataset,
    build_features,
    load_bars,
    trailing_volatility,
    triple_barrier_labels,
)
from trading_bot.research.tesla.evaluate import roc_auc, score_classification
from trading_bot.research.tesla.splits import validation_tail, walk_forward_folds


def _synthetic_bars(n: int = 400, seed: int = 0) -> Bars:
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0, 0.02, size=n)
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = close * (1.0 + rng.normal(0.0, 0.003, size=n))
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.005, size=n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.005, size=n)))
    volume = rng.uniform(1e6, 5e6, size=n)
    start = date(2015, 1, 5)
    dates = [start + timedelta(days=i) for i in range(n)]
    return Bars(dates=dates, open=open_, high=high, low=low, close=close, volume=volume)


# --------------------------------------------------------------------------
# Loading and validation
# --------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_load_bars_reads_ohlcv(tmp_path: Path) -> None:
    path = tmp_path / "ok.csv"
    _write_csv(
        path,
        [
            {"Date": "2020-01-02", "Open": 10, "High": 11, "Low": 9, "Close": 10.5, "Volume": 100},
            {"Date": "2020-01-03", "Open": 10.5, "High": 12, "Low": 10, "Close": 11, "Volume": 120},
        ],
    )
    bars = load_bars(path)
    assert len(bars) == 2
    assert bars.dates[0] == date(2020, 1, 2)
    assert bars.close[-1] == pytest.approx(11.0)


def test_load_bars_rejects_unsorted_dates(tmp_path: Path) -> None:
    path = tmp_path / "unsorted.csv"
    _write_csv(
        path,
        [
            {"Date": "2020-01-03", "Open": 10, "High": 11, "Low": 9, "Close": 10.5, "Volume": 100},
            {"Date": "2020-01-02", "Open": 10, "High": 11, "Low": 9, "Close": 10.5, "Volume": 100},
        ],
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        load_bars(path)


def test_load_bars_rejects_incoherent_ohlc(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    _write_csv(
        path,
        [
            # high below the close: impossible bar
            {"Date": "2020-01-02", "Open": 10, "High": 10.2, "Low": 9, "Close": 10.5, "Volume": 1},
        ],
    )
    with pytest.raises(ValueError, match="incoherent OHLC"):
        load_bars(path)


# --------------------------------------------------------------------------
# Causality — the leakage tests
# --------------------------------------------------------------------------


def test_trailing_volatility_excludes_current_bar() -> None:
    """vol[t] must be knowable before bar t happens."""
    bars = _synthetic_bars(100)
    vol = trailing_volatility(bars.close, span=20)

    tampered = bars.close.copy()
    tampered[60] *= 1.5  # a violent day at index 60
    vol_tampered = trailing_volatility(tampered, span=20)

    # Everything up to and including index 60 is unchanged: bar 60's own
    # move cannot have entered its own scaling constant.
    assert np.allclose(vol[:61], vol_tampered[:61], equal_nan=True)
    assert not np.allclose(vol[61:], vol_tampered[61:], equal_nan=True)


def test_features_do_not_depend_on_future_bars() -> None:
    """Perturbing bar t+1 must leave every feature row <= t untouched."""
    bars = _synthetic_bars(300)
    base = build_features(bars)

    cut = 200
    tampered = Bars(
        dates=bars.dates,
        open=bars.open.copy(),
        high=bars.high.copy(),
        low=bars.low.copy(),
        close=bars.close.copy(),
        volume=bars.volume.copy(),
    )
    for arr in (tampered.open, tampered.high, tampered.low, tampered.close):
        arr[cut + 1 :] *= 1.3
    tampered.volume[cut + 1 :] *= 4.0

    after = build_features(tampered)
    assert np.allclose(base[: cut + 1], after[: cut + 1], equal_nan=True)


def test_dataset_window_ends_at_its_origin() -> None:
    """Sample i's last window row must be the feature row of its origin bar."""
    bars = _synthetic_bars(400)
    data = build_dataset(bars, window=20, horizon=5)
    features = build_features(bars)
    for i in (0, 5, len(data) - 1):
        origin = int(data.origin_index[i])
        assert np.allclose(data.x[i, -1, :], features[origin])
        assert data.dates[i] == bars.dates[origin]


# --------------------------------------------------------------------------
# Labelling
# --------------------------------------------------------------------------


def test_triple_barrier_detects_up_and_down_first_touch() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    # Give the volatility estimator something non-zero to chew on.
    close[:40] = 100.0 * (1.0 + 0.01 * np.sin(np.arange(40)))
    high[:40] = close[:40]
    low[:40] = close[:40]

    bars = Bars(
        dates=[date(2020, 1, 1) + timedelta(days=i) for i in range(n)],
        open=close.copy(),
        high=high,
        low=low,
        close=close,
        volume=np.full(n, 1e6),
    )
    vol = trailing_volatility(bars.close, 20)
    t = 45
    width = 1.0 * vol[t]

    # Day t+2 punches decisively through the upper barrier.
    bars.high[t + 2] = bars.close[t] * np.exp(width * 2.0)
    labels, _ = triple_barrier_labels(bars, horizon=5, k_sigma=1.0)
    assert labels[t] == UP

    # Same setup, but a lower touch arrives first at t+1.
    bars.low[t + 1] = bars.close[t] * np.exp(-width * 2.0)
    labels, _ = triple_barrier_labels(bars, horizon=5, k_sigma=1.0)
    assert labels[t] == DOWN


def test_triple_barrier_returns_neutral_when_no_barrier_touched() -> None:
    bars = _synthetic_bars(200, seed=3)
    # A barrier 50 sigma wide is unreachable within a 5-day horizon.
    labels, _ = triple_barrier_labels(bars, horizon=5, k_sigma=50.0)
    assert set(np.unique(labels)) == {NEUTRAL}


def test_triple_barrier_horizon_end_is_neutral() -> None:
    bars = _synthetic_bars(120)
    labels, _ = triple_barrier_labels(bars, horizon=5, k_sigma=1.0)
    assert all(labels[t] == NEUTRAL for t in range(len(bars) - 5, len(bars)))


# --------------------------------------------------------------------------
# Split hygiene
# --------------------------------------------------------------------------


def test_folds_are_ordered_and_embargoed() -> None:
    embargo = 34
    folds = walk_forward_folds(n_samples=2000, n_folds=5, embargo=embargo, min_train=500)
    assert len(folds) == 5
    for fold in folds:
        assert fold.train.size > 0
        assert fold.test.size > 0
        # Training data strictly precedes the test block...
        assert fold.train.max() < fold.test.min()
        # ...with a full embargo gap between them.
        assert fold.test.min() - fold.train.max() > embargo
        assert len(np.intersect1d(fold.train, fold.test)) == 0


def test_folds_cover_disjoint_test_blocks() -> None:
    folds = walk_forward_folds(n_samples=2000, n_folds=4, embargo=34, min_train=500)
    seen: set[int] = set()
    for fold in folds:
        block = set(int(i) for i in fold.test)
        assert not (block & seen)
        seen |= block


def test_folds_reject_impossible_configuration() -> None:
    with pytest.raises(ValueError, match="not enough samples"):
        walk_forward_folds(n_samples=300, n_folds=5, embargo=34, min_train=500)


def test_validation_tail_purges_between_fit_and_val() -> None:
    train = np.arange(1000, dtype=np.int64)
    fit, val = validation_tail(train, fraction=0.2, embargo=34)
    assert val.size == 200
    assert fit.max() < val.min()
    assert val.min() - fit.max() > 34


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def test_roc_auc_perfect_and_inverted() -> None:
    y = np.array([0, 0, 1, 1], dtype=np.int64)
    assert roc_auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert roc_auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)


def test_roc_auc_constant_predictor_is_half() -> None:
    """A model that always says 0.5 must not score better than a coin flip."""
    y = np.array([0, 1, 0, 1], dtype=np.int64)
    assert roc_auc(y, np.full(4, 0.5)) == pytest.approx(0.5)


def test_positive_control_harness_finds_a_planted_signal() -> None:
    """Guard against a null result caused by a broken pipeline.

    "No edge found" and "the harness cannot find any edge" produce the same
    output, so we plant a signal that IS real — a channel correlated with
    the label — and require the pipeline to recover it through the same
    purged folds and scoring. If this ever fails, every null result the
    study reports becomes uninterpretable.
    """
    from trading_bot.research.tesla.model import LogisticClassifier
    from trading_bot.research.tesla.splits import walk_forward_folds

    bars = _synthetic_bars(1500, seed=11)
    data = build_dataset(bars, window=20, horizon=5)
    tradable = data.tradable

    rng = np.random.default_rng(0)
    x = data.x.copy()
    # Channel 0, last row only: the label plus heavy noise. Detectable but
    # far from trivial — a broken split would show ~0.5 regardless.
    planted = np.where(data.y == UP, 1.0, -1.0) + rng.normal(0.0, 1.0, size=len(data))
    x[:, -1, 0] = planted

    folds = walk_forward_folds(len(data), n_folds=3, embargo=24, min_train=300)
    aucs = []
    for fold in folds:
        train = fold.train[tradable[fold.train]]
        test = fold.test[tradable[fold.test]]
        model = LogisticClassifier()
        model.fit(x[train], data.y[train])
        aucs.append(roc_auc(data.y[test], model.predict_proba_up(x[test])))

    assert min(aucs) > 0.65, f"harness failed to recover a planted signal: {aucs}"


def test_score_classification_counts_confident_calls_only() -> None:
    y = np.array([1, 1, 0, 0], dtype=np.int64)
    p = np.array([0.9, 0.52, 0.1, 0.48])  # two calls clear a 0.55 threshold
    score = score_classification(y, p, threshold=0.55)
    assert score.coverage == pytest.approx(0.5)
    assert score.precision == pytest.approx(1.0)
    assert score.base_rate == pytest.approx(0.5)
