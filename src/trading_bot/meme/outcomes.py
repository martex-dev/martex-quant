"""Measure what actually happened to a registered launch.

Separate from the registry by design: registry rows are written once, at
discovery, and never revised; outcomes are computed later from minute bars and
may be recomputed as more history accrues. Keeping them in different files
makes it structurally impossible for an outcome to contaminate the sampling
frame.

The entry-price rule is the part that matters most and the part that is easiest
to get quietly wrong. A backtest that enters at the price shown in the registry
row is claiming a fill at a price observed in a feed that (a) already lagged the
chain and (b) we only polled up to 90 seconds later. So entry here is the
**open of the first minute bar that starts strictly after our observation
timestamp** — the first price a human or bot reacting to our own feed could
plausibly have paid. On a token doing 3x in ninety seconds that distinction is
the entire result.

Exits are evaluated on bar highs and lows, which is the optimistic side of the
same coin: MFE assumes you sold the exact top. That is stated rather than fixed
because MFE is used here as an upper bound on what any exit rule could have
captured, not as an achievable return.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from trading_bot.meme.sources.geckoterminal import Bar

logger = logging.getLogger(__name__)

# Horizons, in minutes, at which forward outcomes are measured.
HORIZONS_MIN: tuple[int, ...] = (5, 15, 30, 60, 240, 1440)

# A token is called dead once it has lost this much from its entry price and
# never recovers within the horizon. Chosen at 90% because AMM pools do not go
# to exactly zero — liquidity is pulled and the last quoted price lingers.
DEATH_DRAWDOWN = 0.90


@dataclass(frozen=True, slots=True)
class Outcome:
    """Forward result for one launch, measured from a realistic entry."""

    pool_address: str
    entry_at: datetime | None
    entry_price: float | None
    bars_available: int
    minutes_covered: float
    returns: dict[int, float]
    """Close-to-close return at each horizon, as a fraction (0.5 == +50%)."""

    mfe: dict[int, float]
    """Best unrealised gain reachable within the horizon (bar highs)."""

    mae: dict[int, float]
    """Worst unrealised loss suffered within the horizon (bar lows)."""

    minutes_to_peak: float | None
    peak_return: float | None
    died_within_min: int | None
    """First horizon at which the token was down ``DEATH_DRAWDOWN`` or more."""

    reason: str

    @property
    def measurable(self) -> bool:
        return self.entry_price is not None and self.entry_price > 0

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "pool_address": self.pool_address,
            "entry_at": self.entry_at.isoformat() if self.entry_at else None,
            "entry_price": self.entry_price,
            "bars_available": self.bars_available,
            "minutes_covered": self.minutes_covered,
            "minutes_to_peak": self.minutes_to_peak,
            "peak_return": self.peak_return,
            "died_within_min": self.died_within_min,
            "reason": self.reason,
        }
        for horizon in HORIZONS_MIN:
            row[f"ret_{horizon}m"] = self.returns.get(horizon)
            row[f"mfe_{horizon}m"] = self.mfe.get(horizon)
            row[f"mae_{horizon}m"] = self.mae.get(horizon)
        return row


def _empty(pool_address: str, bars: int, reason: str) -> Outcome:
    return Outcome(
        pool_address=pool_address,
        entry_at=None,
        entry_price=None,
        bars_available=bars,
        minutes_covered=0.0,
        returns={},
        mfe={},
        mae={},
        minutes_to_peak=None,
        peak_return=None,
        died_within_min=None,
        reason=reason,
    )


def measure(
    pool_address: str,
    bars: list[Bar],
    observed_at: datetime,
    *,
    horizons_min: tuple[int, ...] = HORIZONS_MIN,
) -> Outcome:
    """Compute forward outcomes for one pool from its minute bars.

    ``bars`` must be chronological (``GeckoTerminalClient.ohlcv`` guarantees
    this). Horizons with no data are simply absent from the result dicts rather
    than filled with zeros — a token that only lived twenty minutes has no
    24-hour return, and pretending otherwise with a 0.0 would bias every
    aggregate that follows.
    """
    if not bars:
        return _empty(pool_address, 0, "no bars returned")

    observed_at = observed_at.astimezone(UTC)
    entry_idx = next((i for i, bar in enumerate(bars) if bar.ts > observed_at), None)
    if entry_idx is None:
        return _empty(pool_address, len(bars), "no bar after observation")

    entry_bar = bars[entry_idx]
    entry_price = entry_bar.open
    if entry_price <= 0:
        return _empty(pool_address, len(bars), "non-positive entry price")

    forward = bars[entry_idx:]
    minutes_covered = (forward[-1].ts - entry_bar.ts).total_seconds() / 60.0

    returns: dict[int, float] = {}
    mfe: dict[int, float] = {}
    mae: dict[int, float] = {}
    died_within: int | None = None

    for horizon in horizons_min:
        cutoff = entry_bar.ts + timedelta(minutes=horizon)
        window = [bar for bar in forward if bar.ts <= cutoff]
        if not window:
            continue
        # Only claim a horizon we actually observed. Without this, a token whose
        # feed stops at minute 30 would report its minute-30 price as its
        # 24-hour outcome, which silently turns "stopped trading" into "flat".
        if minutes_covered + 1.0 < horizon and window[-1].ts < cutoff - timedelta(minutes=1):
            continue
        returns[horizon] = window[-1].close / entry_price - 1.0
        mfe[horizon] = max(bar.high for bar in window) / entry_price - 1.0
        mae[horizon] = min(bar.low for bar in window) / entry_price - 1.0
        if died_within is None and mae[horizon] <= -DEATH_DRAWDOWN:
            died_within = horizon

    peak_return: float | None = None
    minutes_to_peak: float | None = None
    if forward:
        peak_bar = max(forward, key=lambda bar: bar.high)
        peak_return = peak_bar.high / entry_price - 1.0
        minutes_to_peak = (peak_bar.ts - entry_bar.ts).total_seconds() / 60.0

    return Outcome(
        pool_address=pool_address,
        entry_at=entry_bar.ts,
        entry_price=entry_price,
        bars_available=len(bars),
        minutes_covered=minutes_covered,
        returns=returns,
        mfe=mfe,
        mae=mae,
        minutes_to_peak=minutes_to_peak,
        peak_return=peak_return,
        died_within_min=died_within,
        reason="ok",
    )
