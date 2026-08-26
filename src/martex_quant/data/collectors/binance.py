"""Binance spot OHLCV collector via ccxt.

Public market data only — no API keys involved. Pagination walks forward in
exchange-page-sized steps (1000 bars); transient network errors retry with
exponential backoff; ccxt's built-in rate limiter stays enabled so we remain
a polite API citizen.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import ccxt
import polars as pl

from martex_quant.data.collectors.base import BaseCollector
from martex_quant.data.models import Interval, ohlcv_frame_from_rows

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 1000  # Binance max bars per request

# Quote assets we can split a slashless symbol on, longest first so that
# e.g. BTCUSDC does not match quote "BTC".
_KNOWN_QUOTES = ("FDUSD", "USDT", "USDC", "BUSD", "TUSD", "EUR", "TRY", "BTC", "ETH", "BNB")


def to_ccxt_symbol(symbol: str) -> str:
    """Map an exchange-neutral id (``BTCUSDT``) to a ccxt symbol (``BTC/USDT``)."""
    if "/" in symbol:
        return symbol
    for quote in _KNOWN_QUOTES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return f"{symbol[: -len(quote)]}/{quote}"
    raise ValueError(
        f"cannot infer quote asset for {symbol!r}; pass the ccxt form, e.g. 'BTC/USDT'"
    )


class BinanceCollector(BaseCollector):
    def __init__(
        self,
        client: Any | None = None,
        max_retries: int = 5,
        backoff_base_s: float = 1.0,
    ) -> None:
        self._client = client if client is not None else ccxt.binance({"enableRateLimit": True})
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        if start >= end:
            raise ValueError(f"start ({start}) must be before end ({end})")
        ccxt_symbol = to_ccxt_symbol(symbol)
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        rows: list[list[float]] = []
        since = start_ms
        while since < end_ms:
            page = self._fetch_page(ccxt_symbol, interval, since)
            if not page:
                break  # no more data (e.g. instrument listed after `since`)
            rows.extend(page)
            last_ts = int(page[-1][0])
            if last_ts < since:
                raise RuntimeError(f"exchange returned non-advancing page at since={since}")
            since = last_ts + interval.milliseconds
            logger.debug("fetched %d bars up to %d for %s", len(page), last_ts, ccxt_symbol)

        df = ohlcv_frame_from_rows(rows)
        # Exchanges ignore/round `since` in surprising ways; enforce the
        # contract [start, end) ourselves.
        return df.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))

    def _fetch_page(self, ccxt_symbol: str, interval: Interval, since: int) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                result: list[list[float]] = self._client.fetch_ohlcv(
                    ccxt_symbol, timeframe=str(interval), since=since, limit=_PAGE_LIMIT
                )
                return result
            except ccxt.NetworkError as exc:  # includes timeouts and rate-limit protection
                last_error = exc
                delay = self._backoff_base_s * (2**attempt)
                logger.warning(
                    "network error fetching %s (attempt %d/%d), retrying in %.1fs: %s",
                    ccxt_symbol,
                    attempt + 1,
                    self._max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)
        raise RuntimeError(
            f"giving up on {ccxt_symbol} after {self._max_retries} network errors"
        ) from last_error
