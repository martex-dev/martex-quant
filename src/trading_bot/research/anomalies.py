"""Stage 9: anomaly discovery — finding "that's weird".

This subsystem's job is NOT to prove anything. It surfaces observations that
look unusual and records them as **leads**. An anomaly is not a discovery, it
carries no verdict, and it spends no error budget — precisely because nothing
was pre-registered before looking.

The one rule that keeps this honest: an anomaly can only ever become a
finding by being written up as a NEW pre-registered hypothesis and tested on
its own terms. There is deliberately no function here that promotes one.
That is the whole difference between "we noticed something" and "we found
something", and collapsing it is how a lab starts fooling itself at scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import polars as pl


class AnomalyKind(StrEnum):
    VOLATILITY_SHIFT = "volatility_shift"
    CORRELATION_SHIFT = "correlation_shift"
    STRUCTURAL_BREAK = "structural_break"
    DISPERSION_SHIFT = "dispersion_shift"


@dataclass(frozen=True)
class Anomaly:
    """A research LEAD. Never a result.

    ``severity`` is how many robust standard deviations the observation sits
    from its trailing norm. It ranks leads for attention; it is emphatically
    not a p-value and must never be reported as significance.
    """

    kind: AnomalyKind
    at: datetime
    scope: str  # symbol, family, or "cross-section"
    severity: float
    observed: float
    baseline: float
    description: str

    def as_lead(self) -> str:
        return (
            f"[LEAD] {self.kind.value} {self.scope} @ {self.at:%Y-%m-%d}: "
            f"{self.description} (observed {self.observed:.4f} vs baseline "
            f"{self.baseline:.4f}, {self.severity:.1f} robust sd) — "
            "not a finding; requires its own pre-registered hypothesis"
        )


def _robust_z(values: pl.Series, window: int) -> pl.Series:
    """Median/MAD z-score over a trailing window, EXCLUDING the current bar.

    MAD rather than standard deviation because crypto returns are fat-tailed
    enough to make sd-based thresholds meaningless — the same reasoning the
    lake's own outlier validator uses. Excluding the current bar keeps the
    baseline something that was knowable before the observation.
    """
    median = values.shift(1).rolling_median(window)
    mad = (values.shift(1) - median).abs().rolling_median(window)
    scaled = mad * 1.4826  # makes MAD comparable to a normal sd
    # A zero MAD means the trailing window was perfectly flat, and dividing by
    # it yields inf or NaN. Those are NOT filtered here — every caller screens
    # with is_finite(), so a degenerate baseline drops out rather than
    # surfacing a meaningless lead with a nonsense severity.
    return (values - median) / scaled


def detect_volatility_shifts(
    panel: pl.DataFrame,
    *,
    window: int = 90,
    threshold: float = 4.0,
    symbol_column: str = "symbol",
) -> list[Anomaly]:
    """Days where realised volatility jumps far outside its trailing norm."""
    out: list[Anomaly] = []
    for (symbol,), group in panel.sort("day").group_by(symbol_column, maintain_order=True):
        frame = group.with_columns(vol=pl.col("ret").abs())
        frame = frame.with_columns(z=_robust_z(frame["vol"], window))
        flagged = frame.drop_nulls("z").filter(
            pl.col("z").is_finite() & (pl.col("z").abs() > threshold)
        )
        for row in flagged.iter_rows(named=True):
            out.append(
                Anomaly(
                    kind=AnomalyKind.VOLATILITY_SHIFT,
                    at=row["day"],
                    scope=str(symbol),
                    severity=abs(float(row["z"])),
                    observed=float(row["vol"]),
                    baseline=0.0,
                    description="absolute return far outside its trailing norm",
                )
            )
    return out


def detect_dispersion_shifts(
    panel: pl.DataFrame, *, window: int = 90, threshold: float = 4.0
) -> list[Anomaly]:
    """Days when the cross-section spreads out or compresses abnormally.

    Dispersion collapsing means everything is moving together — historically
    the signature of a stress episode, and the condition under which
    cross-sectional strategies have least to pick between.
    """
    daily = (
        panel.drop_nulls("ret")
        .group_by("day")
        .agg(dispersion=pl.col("ret").std(), n=pl.len())
        .filter(pl.col("n") >= 5)
        .sort("day")
    )
    if daily.height <= window:
        return []
    daily = daily.with_columns(z=_robust_z(daily["dispersion"], window))
    flagged = daily.drop_nulls("z").filter(
        pl.col("z").is_finite() & (pl.col("z").abs() > threshold)
    )
    return [
        Anomaly(
            kind=AnomalyKind.DISPERSION_SHIFT,
            at=row["day"],
            scope="cross-section",
            severity=abs(float(row["z"])),
            observed=float(row["dispersion"]),
            baseline=0.0,
            description="cross-sectional dispersion far outside its trailing norm",
        )
        for row in flagged.iter_rows(named=True)
    ]


def detect_correlation_shifts(
    panel: pl.DataFrame,
    *,
    window: int = 90,
    threshold: float = 4.0,
    min_symbols: int = 5,
) -> list[Anomaly]:
    """Days when average pairwise co-movement jumps.

    Approximated by the share of the cross-section moving the same direction
    — cheap, robust, and enough for a lead. A precise correlation matrix
    would be more work for no extra honesty at this stage.
    """
    daily = (
        panel.drop_nulls("ret")
        .group_by("day")
        .agg(
            same_way=((pl.col("ret") > 0).mean() - 0.5).abs() * 2.0,
            n=pl.len(),
        )
        .filter(pl.col("n") >= min_symbols)
        .sort("day")
    )
    if daily.height <= window:
        return []
    daily = daily.with_columns(z=_robust_z(daily["same_way"], window))
    flagged = daily.drop_nulls("z").filter(pl.col("z").is_finite() & (pl.col("z") > threshold))
    return [
        Anomaly(
            kind=AnomalyKind.CORRELATION_SHIFT,
            at=row["day"],
            scope="cross-section",
            severity=float(row["z"]),
            observed=float(row["same_way"]),
            baseline=0.0,
            description="the cross-section moved together far more than usual",
        )
        for row in flagged.iter_rows(named=True)
    ]


def scan(panel: pl.DataFrame, *, window: int = 90, threshold: float = 4.0) -> list[Anomaly]:
    """Run every detector and return leads, most severe first."""
    found = [
        *detect_volatility_shifts(panel, window=window, threshold=threshold),
        *detect_dispersion_shifts(panel, window=window, threshold=threshold),
        *detect_correlation_shifts(panel, window=window, threshold=threshold),
    ]
    return sorted(found, key=lambda a: a.severity, reverse=True)


def summarise(anomalies: list[Anomaly]) -> str:
    if not anomalies:
        return "no anomalies above threshold"
    counts: dict[str, int] = {}
    for a in anomalies:
        counts[a.kind.value] = counts.get(a.kind.value, 0) + 1
    lines = [f"{len(anomalies)} lead(s) — none is a finding:"]
    lines.extend(f"  {kind}: {n}" for kind, n in sorted(counts.items()))
    lines.append(f"  most severe: {anomalies[0].as_lead()}")
    return "\n".join(lines)
