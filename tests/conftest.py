"""Shared test fixtures: a fake ccxt exchange serving a deterministic series.

Also gates the research-extra test modules. `scikit-learn` and `keras` are
deliberately NOT runtime dependencies — they exist only for the H58 ensemble
harness and the TSLA CNN study — so a plain `pip install -e .` plus
requirements-dev.txt has neither. Importing those test modules anyway aborts
the entire collection with a ModuleNotFoundError, which is what a new
contributor gets from the exact commands the README gives them.

Skipping the affected modules keeps the suite runnable everywhere. CI installs
the extra in a separate job, so the coverage is not lost.
"""

from datetime import UTC, datetime
from importlib.util import find_spec

import ccxt


def _installed(module: str) -> bool:
    """True when `module` can be imported, without importing it."""
    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):
        return False


# module -> the import that must resolve for it to be collectable
_RESEARCH_EXTRA_MODULES = {
    "test_ensemble.py": "sklearn",
    "test_tesla_cnn.py": "keras",
}

collect_ignore = [
    module for module, requirement in _RESEARCH_EXTRA_MODULES.items() if not _installed(requirement)
]

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
