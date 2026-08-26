"""Turn the recorded panel into per-launch outcomes.

The panel is a long table of (pool, observation time, state). This module
pivots it into one row per launch with forward returns, excursions and a death
flag, joined to the features that were known at registration.

Three rules encode the anti-leakage discipline, and they are the reason this is
a module with tests rather than a notebook cell:

**Entry is the first panel observation strictly after discovery.** Not the
registry's quoted price - that price was already stale when the feed printed
it, and claiming it as a fill invents an edge worth more than any model.

**A horizon is only reported if it was observed.** If the panel stops before
``entry + H``, the horizon comes back absent rather than carrying the last
known price forward. Carrying forward silently converts "we stopped looking"
into "it went flat", which biases every mean upward.

**Delisting is an outcome, not a missing value.** When the aggregator stops
returning a pool, liquidity has been pulled and a holder cannot realistically
exit. That is recorded as a total loss, not dropped from the sample. Dropping
it would leave a dataset of survivors, which is the exact failure this whole
layer is built to avoid.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HORIZONS_MIN: tuple[int, ...] = (15, 30, 60, 120, 240, 720, 1440)

# Fraction of the nominal horizon that must have elapsed for an observation to
# count as measuring it. Panel passes land on a ~5 minute grid, so an exact hit
# is rare and demanding one would discard almost everything.
HORIZON_TOLERANCE = 0.75

# Loss booked when a pool stops being quoted by the aggregator.
DELISTED_RETURN = -1.0


@dataclass(frozen=True, slots=True)
class Observation:
    at: datetime
    price: float | None
    liquidity: float | None
    alive: bool


@dataclass(frozen=True, slots=True)
class LaunchOutcome:
    pool_address: str
    entry_at: datetime | None
    entry_price: float | None
    entry_liquidity: float | None
    observations: int
    minutes_covered: float
    returns: dict[int, float]
    mfe: dict[int, float]
    mae: dict[int, float]
    peak_return: float | None
    minutes_to_peak: float | None
    delisted_at_min: float | None
    reason: str

    @property
    def measurable(self) -> bool:
        return self.entry_price is not None and self.entry_price > 0

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "pool_address": self.pool_address,
            "entry_at": self.entry_at.isoformat() if self.entry_at else None,
            "entry_price": self.entry_price,
            "entry_liquidity": self.entry_liquidity,
            "observations": self.observations,
            "minutes_covered": self.minutes_covered,
            "peak_return": self.peak_return,
            "minutes_to_peak": self.minutes_to_peak,
            "delisted_at_min": self.delisted_at_min,
            "reason": self.reason,
        }
        for horizon in HORIZONS_MIN:
            row[f"ret_{horizon}m"] = self.returns.get(horizon)
            row[f"mfe_{horizon}m"] = self.mfe.get(horizon)
            row[f"mae_{horizon}m"] = self.mae.get(horizon)
        return row


def read_panel(root: Path) -> dict[str, list[Observation]]:
    """Load every panel partition into per-pool observation series."""
    series: dict[str, list[Observation]] = {}
    for path in sorted(Path(root).glob("*.jsonl")):
        for row in _read_jsonl(path):
            address = row.get("pair_address")
            stamp = row.get("observed_at")
            if not isinstance(address, str) or not isinstance(stamp, str):
                continue
            series.setdefault(address, []).append(
                Observation(
                    at=datetime.fromisoformat(stamp),
                    price=_as_float(row.get("price_usd")),
                    liquidity=_as_float(row.get("liquidity_usd")),
                    alive=bool(row.get("alive")),
                )
            )
    for observations in series.values():
        observations.sort(key=lambda obs: obs.at)
    return series


def measure_launch(
    pool_address: str,
    observations: list[Observation],
    discovered_at: datetime,
    *,
    horizons_min: tuple[int, ...] = HORIZONS_MIN,
) -> LaunchOutcome:
    """Compute forward outcomes for one pool from its panel series."""
    if len(observations) < 2:
        return _empty(pool_address, len(observations), "fewer than 2 observations")

    discovered_at = discovered_at.astimezone(UTC)
    entry_idx = next(
        (
            i
            for i, obs in enumerate(observations)
            if obs.at > discovered_at and obs.alive and obs.price is not None and obs.price > 0
        ),
        None,
    )
    if entry_idx is None:
        return _empty(pool_address, len(observations), "no priceable observation after discovery")

    entry = observations[entry_idx]
    assert entry.price is not None
    entry_price = entry.price
    forward = observations[entry_idx:]
    minutes_covered = (forward[-1].at - entry.at).total_seconds() / 60.0

    # Effective price series: a delisted pool is worth nothing to a holder, so
    # it contributes a total loss from that point rather than a gap.
    path: list[tuple[float, float]] = []
    delisted_at_min: float | None = None
    for obs in forward:
        elapsed = (obs.at - entry.at).total_seconds() / 60.0
        if not obs.alive or obs.price is None or obs.price <= 0:
            if delisted_at_min is None:
                delisted_at_min = elapsed
            # DELISTED_RETURN, not 0.0: this list holds returns, and a delisted
            # pool is a total loss. Writing 0.0 here would book every rug as a
            # flat trade and quietly turn the worst outcome into a neutral one.
            path.append((elapsed, DELISTED_RETURN))
        else:
            path.append((elapsed, obs.price / entry_price - 1.0))

    returns: dict[int, float] = {}
    mfe: dict[int, float] = {}
    mae: dict[int, float] = {}
    for horizon in horizons_min:
        window = [(elapsed, ret) for elapsed, ret in path if elapsed <= horizon]
        if not window:
            continue
        last_elapsed = window[-1][0]
        # Require the window to actually reach near the horizon. Without this,
        # a pool observed for 20 minutes would report its 20-minute state as
        # its 24-hour outcome.
        if last_elapsed < horizon * HORIZON_TOLERANCE:
            continue
        returns[horizon] = max(window[-1][1], DELISTED_RETURN)
        mfe[horizon] = max(ret for _, ret in window)
        mae[horizon] = max(min(ret for _, ret in window), DELISTED_RETURN)

    peak_elapsed, peak_return = max(path, key=lambda item: item[1])

    return LaunchOutcome(
        pool_address=pool_address,
        entry_at=entry.at,
        entry_price=entry_price,
        entry_liquidity=entry.liquidity,
        observations=len(observations),
        minutes_covered=minutes_covered,
        returns=returns,
        mfe=mfe,
        mae=mae,
        peak_return=peak_return,
        minutes_to_peak=peak_elapsed,
        delisted_at_min=delisted_at_min,
        reason="ok",
    )


def _empty(pool_address: str, observations: int, reason: str) -> LaunchOutcome:
    return LaunchOutcome(
        pool_address=pool_address,
        entry_at=None,
        entry_price=None,
        entry_liquidity=None,
        observations=observations,
        minutes_covered=0.0,
        returns={},
        mfe={},
        mae={},
        peak_return=None,
        minutes_to_peak=None,
        delisted_at_min=None,
        reason=reason,
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield row


def panel_span(series: dict[str, list[Observation]]) -> tuple[datetime, datetime] | None:
    """Earliest and latest observation across the whole panel."""
    stamps = [obs.at for observations in series.values() for obs in observations]
    if not stamps:
        return None
    return min(stamps), max(stamps)


def coverage_summary(series: dict[str, list[Observation]]) -> str:
    span = panel_span(series)
    if span is None:
        return "panel empty"
    start, end = span
    hours = (end - start) / timedelta(hours=1)
    return f"{len(series)} pools, {start:%Y-%m-%d %H:%M} -> {end:%H:%M} UTC ({hours:.1f}h)"
