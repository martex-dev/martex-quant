"""Collector tests against a fake ccxt client — no network involved."""

from datetime import UTC, datetime, timedelta

import ccxt
import pytest

from trading_bot.data.collectors.binance import BinanceCollector, to_ccxt_symbol
from trading_bot.data.models import OHLCV_SCHEMA, Interval

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


def make_collector(fake: FakeExchange) -> BinanceCollector:
    return BinanceCollector(client=fake, backoff_base_s=0.0)


def test_single_page_fetch() -> None:
    fake = FakeExchange(START_MS, n_bars=100)
    df = make_collector(fake).fetch_ohlcv(
        "BTCUSDT", Interval.H1, START, START + timedelta(hours=100)
    )
    assert df.height == 100
    assert dict(df.schema) == OHLCV_SCHEMA
    assert df["timestamp"].min() == START
    assert df["timestamp"].is_sorted()


def test_pagination_walks_pages() -> None:
    fake = FakeExchange(START_MS, n_bars=2500)
    df = make_collector(fake).fetch_ohlcv(
        "BTCUSDT", Interval.H1, START, START + timedelta(hours=2500)
    )
    assert df.height == 2500
    assert len(fake.calls) == 3  # 1000 + 1000 + 500
    assert not df["timestamp"].is_duplicated().any()


def test_end_is_exclusive_and_clipped() -> None:
    fake = FakeExchange(START_MS, n_bars=100)
    df = make_collector(fake).fetch_ohlcv(
        "BTCUSDT", Interval.H1, START, START + timedelta(hours=10)
    )
    assert df.height == 10
    assert df["timestamp"].max() == START + timedelta(hours=9)


def test_instrument_listed_after_start_returns_partial() -> None:
    # Data begins 50h after the requested start.
    fake = FakeExchange(START_MS + 50 * H1_MS, n_bars=50)
    df = make_collector(fake).fetch_ohlcv(
        "BTCUSDT", Interval.H1, START, START + timedelta(hours=100)
    )
    assert df.height == 50
    assert df["timestamp"].min() == START + timedelta(hours=50)


def test_retries_transient_network_errors() -> None:
    fake = FakeExchange(START_MS, n_bars=10, fail_first=2)
    df = make_collector(fake).fetch_ohlcv(
        "BTCUSDT", Interval.H1, START, START + timedelta(hours=10)
    )
    assert df.height == 10


def test_gives_up_after_max_retries() -> None:
    fake = FakeExchange(START_MS, n_bars=10, fail_first=99)
    collector = BinanceCollector(client=fake, max_retries=3, backoff_base_s=0.0)
    with pytest.raises(RuntimeError, match="giving up"):
        collector.fetch_ohlcv("BTCUSDT", Interval.H1, START, START + timedelta(hours=10))


def test_invalid_range_rejected() -> None:
    fake = FakeExchange(START_MS, n_bars=10)
    with pytest.raises(ValueError, match="before"):
        make_collector(fake).fetch_ohlcv("BTCUSDT", Interval.H1, START, START)


@pytest.mark.parametrize(
    ("neutral", "ccxt_form"),
    [
        ("BTCUSDT", "BTC/USDT"),
        ("ETHBTC", "ETH/BTC"),
        ("BTCFDUSD", "BTC/FDUSD"),
        ("SOL/USDT", "SOL/USDT"),  # already ccxt form passes through
    ],
)
def test_symbol_mapping(neutral: str, ccxt_form: str) -> None:
    assert to_ccxt_symbol(neutral) == ccxt_form


def test_symbol_mapping_unknown_quote_raises() -> None:
    with pytest.raises(ValueError, match="quote"):
        to_ccxt_symbol("BTCXYZ")
