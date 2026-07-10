"""Collector interface. Every data source implements this and returns the
canonical OHLCV schema, keeping the rest of the system source-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import polars as pl

from trading_bot.data.models import Interval


class BaseCollector(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """Fetch bars with open time in ``[start, end)`` in the canonical schema.

        Implementations own pagination, rate limiting, and transient-error
        retries. ``symbol`` is the exchange-neutral id without a slash
        (e.g. ``BTCUSDT``).
        """
