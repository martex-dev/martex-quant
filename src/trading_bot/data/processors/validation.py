"""OHLCV validation: report problems, never repair them.

``validate_ohlcv`` is a pure function — it inspects a frame and returns a
``ValidationReport``. Any repair (gap filling, dropping bars) is a separate,
explicit decision made by the caller and recorded in the catalog.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

import polars as pl
from pydantic import BaseModel, Field

from trading_bot.data.models import OHLCV_SCHEMA, Interval

# A robust z-score (median/MAD-based) beyond this flags a bar as an outlier.
# MAD is used instead of stdev because crypto returns are fat-tailed enough
# to make stdev-based thresholds meaningless.
MAD_Z_THRESHOLD = 10.0
_MAD_SCALE = 0.6745  # makes MAD-z comparable to a normal z-score
_MAX_EXAMPLES = 5


class Severity(StrEnum):
    ERROR = "error"  # data is unusable or corrupt; do not store/trust it
    WARNING = "warning"  # suspicious; usable but must be understood
    INFO = "info"  # context worth recording


class Finding(BaseModel):
    check: str
    severity: Severity
    message: str
    count: int = 0
    examples: list[datetime] = Field(default_factory=list)


class ValidationReport(BaseModel):
    interval: Interval
    n_rows: int
    start: datetime | None = None
    end: datetime | None = None
    findings: list[Finding] = Field(default_factory=list)

    @property
    def n_errors(self) -> int:
        return sum(f.severity == Severity.ERROR for f in self.findings)

    @property
    def n_warnings(self) -> int:
        return sum(f.severity == Severity.WARNING for f in self.findings)

    @property
    def has_errors(self) -> bool:
        return self.n_errors > 0

    def to_text(self) -> str:
        lines = [
            f"Validation report — interval={self.interval}, rows={self.n_rows}",
            f"Range: {self.start} .. {self.end}",
            f"Result: {self.n_errors} error(s), {self.n_warnings} warning(s)",
        ]
        for f in self.findings:
            lines.append(f"  [{f.severity.upper():7}] {f.check}: {f.message}")
            if f.examples:
                shown = ", ".join(str(ts) for ts in f.examples)
                lines.append(f"            e.g. {shown}")
        if not self.findings:
            lines.append("  All checks passed.")
        return "\n".join(lines)


def validate_ohlcv(
    df: pl.DataFrame,
    interval: Interval,
    requested_start: datetime | None = None,
    requested_end: datetime | None = None,
) -> ValidationReport:
    """Run all validation checks against a canonical OHLCV frame."""
    report = ValidationReport(interval=interval, n_rows=df.height)

    schema_finding = _check_schema(df)
    if schema_finding is not None:
        # Remaining checks assume the canonical schema; stop here.
        report.findings.append(schema_finding)
        return report

    if df.height == 0:
        report.findings.append(
            Finding(check="empty", severity=Severity.ERROR, message="dataset contains no rows")
        )
        return report

    report.start = df["timestamp"].min()  # type: ignore[assignment]
    report.end = df["timestamp"].max()  # type: ignore[assignment]

    checks = [
        _check_nulls(df),
        _check_duplicates(df),
        _check_monotonic(df),
        _check_ohlc_coherence(df),
        _check_gaps(df, interval),
        _check_zero_volume(df),
        _check_outliers(df),
        _check_coverage(report, requested_start, requested_end),
    ]
    report.findings.extend(f for f in checks if f is not None)
    return report


def _check_schema(df: pl.DataFrame) -> Finding | None:
    actual = dict(df.schema)
    if actual == OHLCV_SCHEMA:
        return None
    return Finding(
        check="schema",
        severity=Severity.ERROR,
        message=f"schema mismatch: expected {OHLCV_SCHEMA}, got {actual}",
    )


def _check_nulls(df: pl.DataFrame) -> Finding | None:
    null_rows = df.filter(pl.any_horizontal(pl.all().is_null()))
    if null_rows.height == 0:
        return None
    return Finding(
        check="nulls",
        severity=Severity.ERROR,
        message=f"{null_rows.height} row(s) contain null values",
        count=null_rows.height,
        examples=_examples(null_rows),
    )


def _check_duplicates(df: pl.DataFrame) -> Finding | None:
    dupes = df.filter(pl.col("timestamp").is_duplicated())
    if dupes.height == 0:
        return None
    return Finding(
        check="duplicate_timestamps",
        severity=Severity.ERROR,
        message=f"{dupes.height} row(s) share a timestamp with another row",
        count=dupes.height,
        examples=_examples(dupes.unique(subset="timestamp")),
    )


def _check_monotonic(df: pl.DataFrame) -> Finding | None:
    if df["timestamp"].is_sorted():
        return None
    return Finding(
        check="monotonic_timestamps",
        severity=Severity.ERROR,
        message="timestamps are not sorted ascending",
    )


def _check_ohlc_coherence(df: pl.DataFrame) -> Finding | None:
    bad = df.filter(
        (pl.col("low") > pl.min_horizontal("open", "close"))
        | (pl.col("high") < pl.max_horizontal("open", "close"))
        | (pl.min_horizontal("open", "high", "low", "close") <= 0)
        | (pl.col("volume") < 0)
    )
    if bad.height == 0:
        return None
    return Finding(
        check="ohlc_coherence",
        severity=Severity.ERROR,
        message=(
            f"{bad.height} bar(s) violate OHLC coherence "
            "(low/high bounds, positive prices, non-negative volume)"
        ),
        count=bad.height,
        examples=_examples(bad),
    )


def _check_gaps(df: pl.DataFrame, interval: Interval) -> Finding | None:
    diffs_ms = df["timestamp"].diff().dt.total_milliseconds()
    gap_mask = diffs_ms > interval.milliseconds
    n_gaps = int(gap_mask.sum())
    if n_gaps == 0:
        return None
    missing_bars = int(((diffs_ms.filter(gap_mask) // interval.milliseconds) - 1).sum())
    # A gap's example timestamp is the first bar *after* the hole.
    gap_starts = df.filter(gap_mask.fill_null(False))
    return Finding(
        check="gaps",
        severity=Severity.WARNING,
        message=(
            f"{n_gaps} gap(s) in the {interval} grid, {missing_bars} missing bar(s) total "
            "(exchange downtime is a common benign cause — verify before filling)"
        ),
        count=missing_bars,
        examples=_examples(gap_starts),
    )


def _check_zero_volume(df: pl.DataFrame) -> Finding | None:
    zero = df.filter(pl.col("volume") == 0)
    if zero.height == 0:
        return None
    return Finding(
        check="zero_volume",
        severity=Severity.WARNING,
        message=f"{zero.height} bar(s) have zero volume (legal, but suspicious in liquid markets)",
        count=zero.height,
        examples=_examples(zero),
    )


def _check_outliers(df: pl.DataFrame) -> Finding | None:
    if df.height < 3:
        return None
    returns = df["close"].pct_change()
    med = returns.median()
    mad = (returns - med).abs().median()
    if not isinstance(med, int | float) or not isinstance(mad, int | float) or mad == 0.0:
        return None
    z = (returns - med).abs() * _MAD_SCALE / mad
    outliers = df.filter((z > MAD_Z_THRESHOLD).fill_null(False))
    if outliers.height == 0:
        return None
    return Finding(
        check="return_outliers",
        severity=Severity.WARNING,
        message=(
            f"{outliers.height} bar(s) with |MAD z-score| > {MAD_Z_THRESHOLD} on close-to-close "
            "returns (may be real crashes/squeezes — verify against another source)"
        ),
        count=outliers.height,
        examples=_examples(outliers),
    )


def _check_coverage(
    report: ValidationReport,
    requested_start: datetime | None,
    requested_end: datetime | None,
) -> Finding | None:
    if requested_start is None and requested_end is None:
        return None
    parts = []
    if requested_start is not None and report.start is not None and report.start > requested_start:
        parts.append(
            f"data starts {report.start}, {requested_start} was requested "
            "(instrument may not have existed yet)"
        )
    if requested_end is not None and report.end is not None:
        parts.append(f"data ends {report.end} (requested up to {requested_end})")
    if not parts:
        return None
    return Finding(check="coverage", severity=Severity.INFO, message="; ".join(parts))


def _examples(df: pl.DataFrame) -> list[datetime]:
    return df["timestamp"].head(_MAX_EXAMPLES).to_list()
