"""Walk-forward splitter tests: window math is where data leaks hide."""

import pytest

from martex_quant.backtesting.walkforward import walk_forward_windows


def test_basic_tiling_no_overlap_full_oos_coverage() -> None:
    windows = walk_forward_windows(n_bars=100, train_size=40, test_size=20)
    assert len(windows) == 3
    for w in windows:
        assert w.train_end - w.train_start == 40
        assert w.test_end - w.test_start == 20
        assert w.test_start == w.train_end  # test begins where train ends

    # Consecutive test windows tile with no gaps and no overlap:
    assert [(w.test_start, w.test_end) for w in windows] == [(40, 60), (60, 80), (80, 100)]


def test_train_never_reaches_into_test() -> None:
    for w in walk_forward_windows(500, train_size=100, test_size=50):
        assert w.train_end <= w.test_start


def test_custom_step_overlapping_tests() -> None:
    windows = walk_forward_windows(100, train_size=40, test_size=20, step=10)
    assert [(w.test_start, w.test_end) for w in windows][:3] == [(40, 60), (50, 70), (60, 80)]


def test_insufficient_data_rejected() -> None:
    with pytest.raises(ValueError, match="not enough data"):
        walk_forward_windows(50, train_size=40, test_size=20)


def test_invalid_sizes_rejected() -> None:
    with pytest.raises(ValueError):
        walk_forward_windows(100, train_size=0, test_size=20)
    with pytest.raises(ValueError):
        walk_forward_windows(100, train_size=40, test_size=-5)
    with pytest.raises(ValueError):
        walk_forward_windows(100, train_size=40, test_size=20, step=0)


def test_exact_fit_single_window() -> None:
    windows = walk_forward_windows(60, train_size=40, test_size=20)
    assert len(windows) == 1
    assert windows[0].test_end == 60
