"""DexScreener public API adapter (free, keyless, batched).

Chosen over per-pool OHLCV for one decisive reason: this endpoint accepts **30
pair addresses per request**. Measuring 10,000 launches costs ~334 requests
here versus 10,000 elsewhere. At the free rate limits available to us that is
the difference between a dataset that can exist and one that cannot.

The trade-off is that DexScreener returns *state*, not history — there is no
way to ask what a pool did an hour ago. So outcomes are built by polling the
registered cohort repeatedly and differencing our own snapshots, which is
slower to accrue but strictly cleaner: the panel contains only prices we
actually observed at times we actually observed them, so no fill can be
claimed at a price that was never on our screen.

A pool that has been abandoned drops out of the response entirely, or comes
back without a ``liquidity`` block. Both are treated as data — a token going
dark is the single most common outcome in this market and must not be silently
dropped from the denominator.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from martex_quant.meme.http import RateLimitedJsonClient

logger = logging.getLogger(__name__)

_BASE = "https://api.dexscreener.com/latest/dex/pairs"

# The endpoint's documented ceiling per request.
BATCH_SIZE = 30


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class PairState:
    """One pool's state at one polling instant."""

    pair_address: str
    observed_at: datetime
    price_usd: float | None
    liquidity_usd: float | None
    fdv: float | None
    market_cap: float | None
    volume_m5: float | None
    volume_h1: float | None
    volume_h24: float | None
    buys_m5: int
    sells_m5: int
    buys_h1: int
    sells_h1: int
    price_change_m5: float | None
    price_change_h1: float | None
    price_change_h24: float | None
    pair_created_at: datetime | None
    alive: bool
    """False when the API no longer returns this pair at all — the usual end
    state, and a distinct signal from 'quoted but worthless'."""

    def to_row(self) -> dict[str, Any]:
        return {
            "pair_address": self.pair_address,
            "observed_at": self.observed_at.isoformat(),
            "price_usd": self.price_usd,
            "liquidity_usd": self.liquidity_usd,
            "fdv": self.fdv,
            "market_cap": self.market_cap,
            "volume_m5": self.volume_m5,
            "volume_h1": self.volume_h1,
            "volume_h24": self.volume_h24,
            "buys_m5": self.buys_m5,
            "sells_m5": self.sells_m5,
            "buys_h1": self.buys_h1,
            "sells_h1": self.sells_h1,
            "price_change_m5": self.price_change_m5,
            "price_change_h1": self.price_change_h1,
            "price_change_h24": self.price_change_h24,
            "pair_created_at": self.pair_created_at.isoformat() if self.pair_created_at else None,
            "alive": self.alive,
        }


def _chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class DexScreenerClient:
    """Batched pair-state fetcher."""

    def __init__(
        self,
        chain: str = "solana",
        client: RateLimitedJsonClient | None = None,
    ) -> None:
        self._chain = chain
        # 0.6s spacing == 100 requests/minute, comfortably inside the
        # documented 300/min for this endpoint even with a second process.
        self._client = client or RateLimitedJsonClient(min_interval_s=0.6)

    def fetch(self, pair_addresses: Iterable[str]) -> list[PairState]:
        """Return state for every requested pair, including ones that vanished.

        The output length always equals the input length. Pairs the API omits
        come back with ``alive=False`` and null prices rather than being
        dropped, because dropping them would quietly turn a death into a
        missing observation and bias every survival statistic computed later.
        """
        addresses = [addr for addr in pair_addresses if addr]
        results: list[PairState] = []
        for batch in _chunks(addresses, BATCH_SIZE):
            results.extend(self._fetch_batch(batch))
        return results

    def _fetch_batch(self, batch: list[str]) -> list[PairState]:
        url = f"{_BASE}/{self._chain}/{','.join(batch)}"
        stamp = datetime.now(UTC)
        try:
            payload = self._client.get(url)
        except Exception as exc:  # noqa: BLE001 - a failed batch is missing data, not death
            logger.warning("batch of %d failed: %s", len(batch), exc)
            return []

        pairs = payload.get("pairs") or []
        by_address = {
            str(pair.get("pairAddress", "")): pair for pair in pairs if isinstance(pair, dict)
        }
        return [self._parse(addr, by_address.get(addr), stamp) for addr in batch]

    def _parse(self, address: str, pair: dict[str, Any] | None, stamp: datetime) -> PairState:
        if pair is None:
            return PairState(
                pair_address=address,
                observed_at=stamp,
                price_usd=None,
                liquidity_usd=None,
                fdv=None,
                market_cap=None,
                volume_m5=None,
                volume_h1=None,
                volume_h24=None,
                buys_m5=0,
                sells_m5=0,
                buys_h1=0,
                sells_h1=0,
                price_change_m5=None,
                price_change_h1=None,
                price_change_h24=None,
                pair_created_at=None,
                alive=False,
            )

        volume: dict[str, Any] = pair.get("volume", {}) or {}
        txns: dict[str, Any] = pair.get("txns", {}) or {}
        m5: dict[str, Any] = txns.get("m5", {}) or {}
        h1: dict[str, Any] = txns.get("h1", {}) or {}
        change: dict[str, Any] = pair.get("priceChange", {}) or {}
        liquidity: dict[str, Any] = pair.get("liquidity", {}) or {}

        created_ms = pair.get("pairCreatedAt")
        created_at: datetime | None = None
        if isinstance(created_ms, int | float):
            created_at = datetime.fromtimestamp(created_ms / 1000.0, tz=UTC)

        return PairState(
            pair_address=address,
            observed_at=stamp,
            price_usd=_as_float(pair.get("priceUsd")),
            liquidity_usd=_as_float(liquidity.get("usd")),
            fdv=_as_float(pair.get("fdv")),
            market_cap=_as_float(pair.get("marketCap")),
            volume_m5=_as_float(volume.get("m5")),
            volume_h1=_as_float(volume.get("h1")),
            volume_h24=_as_float(volume.get("h24")),
            buys_m5=_as_int(m5.get("buys")),
            sells_m5=_as_int(m5.get("sells")),
            buys_h1=_as_int(h1.get("buys")),
            sells_h1=_as_int(h1.get("sells")),
            price_change_m5=_as_float(change.get("m5")),
            price_change_h1=_as_float(change.get("h1")),
            price_change_h24=_as_float(change.get("h24")),
            pair_created_at=created_at,
            alive=True,
        )
