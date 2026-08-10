"""Purged, embargoed walk-forward splits.

Why not ``train_test_split(shuffle=True)``: consecutive samples share
``window - 1`` of their bars and their labels are resolved over
overlapping future windows. Shuffling puts near-identical rows on both
sides of the split, and the model scores brilliantly by recognising rows
it has effectively already seen. That single line is the most common
reason published "N% accuracy" stock-prediction results do not survive
replication.

So: test blocks always come AFTER their training data in time, and a gap
of ``window + horizon - 1`` samples is purged from the training set on
each side of every test block. That gap is exactly the reach of the
overlap — a training sample outside it can share neither an input bar nor
a labelling bar with any test sample.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold, as index arrays into the dataset."""

    index: int
    train: IntArray
    test: IntArray

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Fold(index={self.index}, n_train={self.train.size}, n_test={self.test.size})"


def walk_forward_folds(
    n_samples: int,
    n_folds: int,
    embargo: int,
    min_train: int = 250,
    expanding: bool = True,
) -> list[Fold]:
    """Split ``n_samples`` ordered samples into purged walk-forward folds.

    The tail of the series is divided into ``n_folds`` contiguous test
    blocks. Each fold trains on samples that end at least ``embargo``
    before its test block starts, and — because a later training sample
    could still overlap an earlier test block when ``expanding`` is used —
    also drops anything within ``embargo`` after a test block it contains.

    ``embargo`` should be ``window + horizon - 1`` for the dataset in use.
    """
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")
    if embargo < 0:
        raise ValueError("embargo must be >= 0")
    if min_train < 1:
        raise ValueError("min_train must be >= 1")

    usable = n_samples - min_train - embargo
    if usable < n_folds:
        raise ValueError(
            f"not enough samples: {n_samples} rows leave {usable} for {n_folds} test blocks "
            f"(min_train={min_train}, embargo={embargo})"
        )

    block = usable // n_folds
    folds: list[Fold] = []
    for i in range(n_folds):
        test_start = min_train + embargo + i * block
        test_end = n_samples if i == n_folds - 1 else test_start + block
        test = np.arange(test_start, test_end, dtype=np.int64)

        train_end = test_start - embargo
        train_start = 0 if expanding else max(0, train_end - min_train)
        train = np.arange(train_start, train_end, dtype=np.int64)

        folds.append(Fold(index=i, train=train, test=test))
    return folds


def validation_tail(train: IntArray, fraction: float, embargo: int) -> tuple[IntArray, IntArray]:
    """Carve an early-stopping validation set off the END of a training block.

    The validation slice is the most recent part of the training data, and
    an embargo is purged between the two so that early stopping is not
    itself tuned on samples overlapping the fitting data.
    """
    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must be in (0, 1)")
    n_val = int(round(train.size * fraction))
    if n_val < 1 or train.size - n_val - embargo < 1:
        raise ValueError("training block too small to carve a validation tail")
    val = train[train.size - n_val :]
    fit = train[: train.size - n_val - embargo]
    return fit, val
