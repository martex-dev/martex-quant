"""Tests for the resampler and index builders (V2 M1 foundations)."""

from datetime import UTC, datetime

import polars as pl
import pytest

from martex_quant.data.indices import dominance_series, equal_weight_index
from martex_quant.data.models import Interval, ohlcv_frame_from_rows
from martex_quant.data.resample import resample_ohlcv

START = datetime(2024, 1, 1, tzinfo=UTC)  # midnight UTC: epoch-aligned
H1_MS = 3_600_000
DAY_MS = 86_400_000


def hourly_frame(n: int, start_ms: int | None = None) -> pl.DataFrame:
    start = int(START.timestamp() * 1000) if start_ms is None else start_ms
    rows = [[start + i * H1_MS, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0] for i in range(n)]
    return ohlcv_frame_from_rows(rows)


def daily_frame(closes: list[float], start_offset_days: int = 0) -> pl.DataFrame:
    start = int(START.timestamp() * 1000) + start_offset_days * DAY_MS
    rows = [[start + i * DAY_MS, c, c, c, c, 1.0] for i, c in enumerate(closes)]
    return ohlcv_frame_from_rows(rows)


# --- resampler ----------------------------------------------------------------


def test_resample_1h_to_6h_hand_checked() -> None:
    df = resample_ohlcv(hourly_frame(12), Interval.H1, Interval.H6)
    assert df.height == 2
    first = df.row(0, named=True)
    assert first["open"] == 100.0  # hour 0 open
    assert first["high"] == 106.0  # hour 5 high
    assert first["low"] == 99.0  # hour 0 low
    assert first["close"] == 105.5  # hour 5 close
    assert first["volume"] == 60.0
    assert df["timestamp"][1] == datetime(2024, 1, 1, 6, tzinfo=UTC)


def test_resample_drops_incomplete_buckets() -> None:
    # 10 hours: one full 6h bucket, one partial (4 bars) — partial dropped.
    df = resample_ohlcv(hourly_frame(10), Interval.H1, Interval.H6)
    assert df.height == 1


def test_resample_12h_alignment() -> None:
    df = resample_ohlcv(hourly_frame(48), Interval.H1, Interval.H12)
    assert df.height == 4
    assert df["timestamp"].to_list()[:2] == [
        datetime(2024, 1, 1, 0, tzinfo=UTC),
        datetime(2024, 1, 1, 12, tzinfo=UTC),
    ]


def test_resample_rejects_bad_combinations() -> None:
    df = hourly_frame(24)
    with pytest.raises(ValueError, match="coarser"):
        resample_ohlcv(df, Interval.H1, Interval.H1)
    with pytest.raises(ValueError, match="coarser"):
        resample_ohlcv(df, Interval.H4, Interval.H6)  # 6h not a multiple of 4h
    with pytest.raises(ValueError, match="schema"):
        resample_ohlcv(pl.DataFrame({"x": [1]}), Interval.H1, Interval.H6)


# --- equal-weight index --------------------------------------------------------


def test_ew_index_two_symbols_hand_computed() -> None:
    # Day1: A +10%, B -10% -> mean 0%. Day2: A +10%, B +30% -> mean +20%.
    frames = {
        "A": daily_frame([100.0, 110.0, 121.0]),
        "B": daily_frame([200.0, 180.0, 234.0]),
    }
    idx = equal_weight_index(frames)
    levels = idx["level"].to_list()
    assert levels[0] == pytest.approx(100.0)
    assert levels[1] == pytest.approx(100.0)
    assert levels[2] == pytest.approx(120.0)


def test_ew_index_listing_aware() -> None:
    # B lists on day 2 (offset 2): until then the index is just A.
    frames = {
        "A": daily_frame([100.0, 110.0, 121.0, 133.1]),  # +10% each day
        "B": daily_frame([50.0, 55.0], start_offset_days=2),  # +10% on day 3
    }
    idx = equal_weight_index(frames)
    levels = idx["level"].to_list()
    assert levels[1] == pytest.approx(110.0)  # A alone
    # Day 2: A +10%; B has no prior close -> excluded, index +10%.
    assert levels[2] == pytest.approx(121.0)
    # Day 3: both +10% -> +10%.
    assert levels[3] == pytest.approx(133.1)


def test_ew_index_requires_symbols() -> None:
    with pytest.raises(ValueError):
        equal_weight_index({})


# --- dominance ------------------------------------------------------------------


def test_dominance_rises_when_btc_outperforms() -> None:
    btc = daily_frame([100.0, 120.0, 150.0])
    alts = {"X": daily_frame([100.0, 100.0, 100.0])}
    dom = dominance_series(btc, equal_weight_index(alts))
    values = dom["dominance"].to_list()
    assert values[0] < values[1] < values[2]
    assert values[0] == pytest.approx(1.0)  # 100 / level-100
