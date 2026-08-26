"""Validator tests: clean data passes; each corruption triggers its check."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from martex_quant.data.models import Interval, ohlcv_frame_from_rows
from martex_quant.data.processors.validation import Severity, validate_ohlcv

START = datetime(2024, 1, 1, tzinfo=UTC)
H1_MS = 3_600_000


def make_clean_frame(n_bars: int = 100, start: datetime = START) -> pl.DataFrame:
    """A gapless 1h series with mild price movement around 100."""
    start_ms = int(start.timestamp() * 1000)
    rows: list[list[float]] = []
    price = 100.0
    for i in range(n_bars):
        drift = 0.1 if i % 2 == 0 else -0.1  # small alternating moves
        close = price + drift
        rows.append(
            [
                start_ms + i * H1_MS,
                price,
                max(price, close) + 0.05,
                min(price, close) - 0.05,
                close,
                1000.0 + i,
            ]
        )
        price = close
    return ohlcv_frame_from_rows(rows)


def finding_checks(df: pl.DataFrame, **kwargs: object) -> set[str]:
    report = validate_ohlcv(df, Interval.H1, **kwargs)  # type: ignore[arg-type]
    return {f.check for f in report.findings}


def test_clean_data_passes() -> None:
    report = validate_ohlcv(make_clean_frame(), Interval.H1)
    assert report.findings == []
    assert not report.has_errors
    assert report.n_rows == 100


def test_empty_frame_is_error() -> None:
    report = validate_ohlcv(make_clean_frame(0), Interval.H1)
    assert report.has_errors
    assert {f.check for f in report.findings} == {"empty"}


def test_schema_mismatch_is_error_and_short_circuits() -> None:
    df = pl.DataFrame({"timestamp": [1, 2], "close": [1.0, 2.0]})
    report = validate_ohlcv(df, Interval.H1)
    assert [f.check for f in report.findings] == ["schema"]
    assert report.has_errors


def test_duplicate_timestamps_detected() -> None:
    df = make_clean_frame()
    df = pl.concat([df, df.tail(1)]).sort("timestamp")
    checks = finding_checks(df)
    assert "duplicate_timestamps" in checks


def test_unsorted_timestamps_detected() -> None:
    df = make_clean_frame().reverse()
    assert "monotonic_timestamps" in finding_checks(df)


def test_null_values_detected() -> None:
    df = make_clean_frame()
    df = df.with_columns(
        pl.when(pl.arange(0, df.height) == 5).then(None).otherwise(pl.col("close")).alias("close")
    )
    assert "nulls" in finding_checks(df)


def test_ohlc_incoherence_detected() -> None:
    df = make_clean_frame()
    # Corrupt one bar: high below close.
    df = df.with_columns(
        pl.when(pl.arange(0, df.height) == 10)
        .then(pl.col("close") - 50)
        .otherwise(pl.col("high"))
        .alias("high")
    )
    report = validate_ohlcv(df, Interval.H1)
    coherence = [f for f in report.findings if f.check == "ohlc_coherence"]
    assert len(coherence) == 1
    assert coherence[0].severity == Severity.ERROR
    assert coherence[0].count == 1


def test_negative_price_detected() -> None:
    df = make_clean_frame()
    df = df.with_columns(
        pl.when(pl.arange(0, df.height) == 3).then(-1.0).otherwise(pl.col("low")).alias("low")
    )
    assert "ohlc_coherence" in finding_checks(df)


def test_gap_detected_with_missing_bar_count() -> None:
    df = make_clean_frame()
    # Remove 3 consecutive bars -> one gap, three missing bars.
    df = df.filter(~pl.arange(0, df.height).is_between(20, 22))
    report = validate_ohlcv(df, Interval.H1)
    gaps = [f for f in report.findings if f.check == "gaps"]
    assert len(gaps) == 1
    assert gaps[0].severity == Severity.WARNING
    assert gaps[0].count == 3
    assert not report.has_errors  # gaps warn, they do not fail


def test_zero_volume_detected() -> None:
    df = make_clean_frame()
    df = df.with_columns(
        pl.when(pl.arange(0, df.height) == 7).then(0.0).otherwise(pl.col("volume")).alias("volume")
    )
    assert "zero_volume" in finding_checks(df)


def test_return_outlier_detected() -> None:
    df = make_clean_frame(200)
    # One bar with a 50% crash amid ~0.1% moves.
    df = df.with_columns(
        pl.when(pl.arange(0, df.height) == 100)
        .then(pl.col("close") * 0.5)
        .otherwise(pl.col("close"))
        .alias("close"),
    )
    # Keep OHLC coherent for the corrupted bar so only the outlier check fires.
    df = df.with_columns(
        low=pl.min_horizontal("low", "close"),
        high=pl.max_horizontal("high", "close"),
        open=pl.col("open"),
    )
    checks = finding_checks(df)
    assert "return_outliers" in checks
    assert "ohlc_coherence" not in checks


def test_coverage_reported_when_data_starts_late() -> None:
    df = make_clean_frame()
    report = validate_ohlcv(
        df,
        Interval.H1,
        requested_start=START - timedelta(days=365),
        requested_end=START + timedelta(days=30),
    )
    coverage = [f for f in report.findings if f.check == "coverage"]
    assert len(coverage) == 1
    assert coverage[0].severity == Severity.INFO


def test_report_text_renders() -> None:
    report = validate_ohlcv(make_clean_frame(), Interval.H1)
    text = report.to_text()
    assert "All checks passed" in text
    assert "rows=100" in text


@pytest.mark.parametrize("interval", list(Interval))
def test_interval_durations_are_positive(interval: Interval) -> None:
    assert interval.milliseconds > 0
