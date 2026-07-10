"""Walk-forward window splitting.

Generates chronological (train, test) index windows: fit/tune on train,
evaluate untouched on test, roll forward. The Phase 3 research harness runs
strategies per window; this module only owns the split math — which is
exactly the kind of code that silently leaks data when written casually.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardWindow:
    """Half-open index ranges: train is [train_start, train_end),
    test is [test_start, test_end), and test always starts where train ends."""

    train_start: int
    train_end: int
    test_start: int
    test_end: int


def walk_forward_windows(
    n_bars: int,
    train_size: int,
    test_size: int,
    step: int | None = None,
) -> list[WalkForwardWindow]:
    """Split ``n_bars`` into rolling train/test windows.

    ``step`` defaults to ``test_size`` so consecutive test windows tile the
    data without overlap — every out-of-sample bar is used exactly once.
    """
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step is None else step
    if step <= 0:
        raise ValueError("step must be positive")
    if train_size + test_size > n_bars:
        raise ValueError(f"not enough data: need >= {train_size + test_size} bars, have {n_bars}")

    windows = []
    start = 0
    while start + train_size + test_size <= n_bars:
        windows.append(
            WalkForwardWindow(
                train_start=start,
                train_end=start + train_size,
                test_start=start + train_size,
                test_end=start + train_size + test_size,
            )
        )
        start += step
    return windows
