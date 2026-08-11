"""GeckoTerminal public API adapter (free, keyless, ~30 requests/minute).

Two endpoints carry this whole research layer:

``/networks/{net}/new_pools``
    The newest DEX pools, 20 per page, up to 10 pages. On Solana that window
    spans roughly the last five minutes — pools are created at ~3,000/hour —
    so capturing the full launch stream means polling faster than the window
    slides. Each listing already carries price, reserve, volume and buy/sell
    counts, so registering a launch costs no extra request.

``/networks/{net}/pools/{addr}/ohlcv/{timeframe}``
    Minute bars back to the pool's birth. This is what makes forward outcomes
    (return, max favourable/adverse excursion, death) measurable after the fact
    without having watched the token tick by tick.

Deliberate limitation, stated once so it is not forgotten downstream: this API
exposes no per-wallet data. Holder concentration, creator history and bundled
buys are invisible here and need a Solana RPC / indexer with a key.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from trading_bot.meme.http import RateLimitedJsonClient

logger = logging.getLogger(__name__)

_BASE = "https://api.geckoterminal.com/api/v2"
_ACCEPT = "application/json;version=20230302"

# The API caps new_pools pagination at 10; asking for more returns an error.
MAX_NEW_POOL_PAGES = 10


def _as_float(value: Any) -> float | None:
    """Coerce an API scalar to float, mapping absent/blank/garbage to None.

    New pools routinely report nulls and empty strings for market cap and
    price fields in their first seconds of life, so this is the common path,
    not an error path.
    """
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
class PoolSnapshot:
    """One pool as the API described it at a single observation time.

    ``observed_at`` is our clock, ``created_at`` is the chain's. The gap
    between them is the pool's age at observation, which is the axis every
    early-life feature in this layer is defined on.
    """

    pool_address: str
    network: str
    name: str
    dex: str
    base_token: str
    quote_token: str
    created_at: datetime | None
    observed_at: datetime
    price_usd: float | None
    fdv_usd: float | None
    market_cap_usd: float | None
    reserve_usd: float | None
    volume_m5: float | None
    volume_h1: float | None
    volume_h24: float | None
    buys_m5: int
    sells_m5: int
    buyers_m5: int
    sellers_m5: int
    buys_h1: int
    sells_h1: int
    price_change_m5: float | None
    price_change_h1: float | None

    @property
    def age_s(self) -> float | None:
        """Seconds between pool creation and this observation."""
        if self.created_at is None:
            return None
        return (self.observed_at - self.created_at).total_seconds()

    def to_row(self) -> dict[str, Any]:
        """Flatten to a JSON-serialisable record for the launch registry."""
        return {
            "pool_address": self.pool_address,
            "network": self.network,
            "name": self.name,
            "dex": self.dex,
            "base_token": self.base_token,
            "quote_token": self.quote_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "observed_at": self.observed_at.isoformat(),
            "age_s": self.age_s,
            "price_usd": self.price_usd,
            "fdv_usd": self.fdv_usd,
            "market_cap_usd": self.market_cap_usd,
            "reserve_usd": self.reserve_usd,
            "volume_m5": self.volume_m5,
            "volume_h1": self.volume_h1,
            "volume_h24": self.volume_h24,
            "buys_m5": self.buys_m5,
            "sells_m5": self.sells_m5,
            "buyers_m5": self.buyers_m5,
            "sellers_m5": self.sellers_m5,
            "buys_h1": self.buys_h1,
            "sells_h1": self.sells_h1,
            "price_change_m5": self.price_change_m5,
            "price_change_h1": self.price_change_h1,
        }


@dataclass(frozen=True, slots=True)
class Bar:
    """One OHLCV bar. ``volume`` is quote-currency (USD) turnover."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _parse_created_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _relationship_id(pool: dict[str, Any], key: str) -> str:
    """Pull a related entity id (e.g. ``solana_So111...``) out of a pool record."""
    rel = pool.get("relationships", {}).get(key, {}).get("data")
    if isinstance(rel, dict):
        return str(rel.get("id", ""))
    return ""


class GeckoTerminalClient:
    """Thin, typed wrapper over the two endpoints this layer needs."""

    def __init__(
        self, network: str = "solana", client: RateLimitedJsonClient | None = None
    ) -> None:
        self._network = network
        self._client = client or RateLimitedJsonClient(min_interval_s=2.2, accept=_ACCEPT)

    @property
    def network(self) -> str:
        return self._network

    def new_pools(
        self, page: int = 1, *, observed_at: datetime | None = None
    ) -> list[PoolSnapshot]:
        """Return one page of the newest pools, newest first.

        ``observed_at`` is injectable so tests can pin the clock; in production
        it is stamped at parse time, which is within a second or two of the
        response and well inside the resolution we care about.
        """
        if not 1 <= page <= MAX_NEW_POOL_PAGES:
            raise ValueError(f"page must be in 1..{MAX_NEW_POOL_PAGES}, got {page}")
        payload = self._client.get(f"{_BASE}/networks/{self._network}/new_pools?page={page}")
        stamp = observed_at or datetime.now(UTC)
        return [self._parse_pool(item, stamp) for item in payload.get("data", [])]

    def _parse_pool(self, item: dict[str, Any], observed_at: datetime) -> PoolSnapshot:
        attrs: dict[str, Any] = item.get("attributes", {})
        volume: dict[str, Any] = attrs.get("volume_usd", {}) or {}
        txns: dict[str, Any] = attrs.get("transactions", {}) or {}
        m5: dict[str, Any] = txns.get("m5", {}) or {}
        h1: dict[str, Any] = txns.get("h1", {}) or {}
        change: dict[str, Any] = attrs.get("price_change_percentage", {}) or {}
        return PoolSnapshot(
            pool_address=str(attrs.get("address", "")),
            network=self._network,
            name=str(attrs.get("name", "")),
            dex=_relationship_id(item, "dex"),
            base_token=_relationship_id(item, "base_token"),
            quote_token=_relationship_id(item, "quote_token"),
            created_at=_parse_created_at(attrs.get("pool_created_at")),
            observed_at=observed_at,
            price_usd=_as_float(attrs.get("base_token_price_usd")),
            fdv_usd=_as_float(attrs.get("fdv_usd")),
            market_cap_usd=_as_float(attrs.get("market_cap_usd")),
            reserve_usd=_as_float(attrs.get("reserve_in_usd")),
            volume_m5=_as_float(volume.get("m5")),
            volume_h1=_as_float(volume.get("h1")),
            volume_h24=_as_float(volume.get("h24")),
            buys_m5=_as_int(m5.get("buys")),
            sells_m5=_as_int(m5.get("sells")),
            buyers_m5=_as_int(m5.get("buyers")),
            sellers_m5=_as_int(m5.get("sellers")),
            buys_h1=_as_int(h1.get("buys")),
            sells_h1=_as_int(h1.get("sells")),
            price_change_m5=_as_float(change.get("m5")),
            price_change_h1=_as_float(change.get("h1")),
        )

    def ohlcv(
        self,
        pool_address: str,
        *,
        timeframe: str = "minute",
        aggregate: int = 1,
        limit: int = 1000,
        before_timestamp: int | None = None,
    ) -> list[Bar]:
        """Return bars for a pool, oldest first.

        The API answers newest-first and caps ``limit`` at 1000; we reverse so
        that downstream code can assume chronological order, which is what
        every excursion calculation wants.
        """
        url = (
            f"{_BASE}/networks/{self._network}/pools/{pool_address}/ohlcv/{timeframe}"
            f"?aggregate={aggregate}&limit={limit}&currency=usd"
        )
        if before_timestamp is not None:
            url += f"&before_timestamp={before_timestamp}"
        payload = self._client.get(url)
        rows = payload.get("data", {}).get("attributes", {}).get("ohlcv_list", []) or []
        bars: list[Bar] = []
        for row in rows:
            if len(row) < 6:
                continue
            bars.append(
                Bar(
                    ts=datetime.fromtimestamp(int(row[0]), tz=UTC),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        bars.sort(key=lambda bar: bar.ts)
        return bars
