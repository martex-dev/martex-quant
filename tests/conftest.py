"""Shared test fixtures: a fake ccxt exchange serving a deterministic series."""

from datetime import UTC, datetime

import ccxt

H1_MS = 3_600_000
START = datetime(2024, 1, 1, tzinfo=UTC)
START_MS = int(START.timestamp() * 1000)


class FakeExchange:
    """Serves a fixed 1h series the way ccxt's binance client would."""

    def __init__(self, first_ms: int, n_bars: int, fail_first: int = 0) -> None:
        self.bars = [
            [float(first_ms + i * H1_MS), 100.0, 101.0, 99.0, 100.5, 10.0] for i in range(n_bars)
        ]
        self.calls: list[int] = []
        self._failures_left = fail_first

    def fetch_ohlcv(self, symbol: str, timeframe: str, since: int, limit: int) -> list[list[float]]:
        if self._failures_left > 0:
            self._failures_left -= 1
            raise ccxt.NetworkError("simulated timeout")
        self.calls.append(since)
        return [b for b in self.bars if b[0] >= since][:limit]
