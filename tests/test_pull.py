"""End-to-end pipeline test with a fake exchange: collect -> validate -> store."""

import json
from datetime import UTC, datetime
from pathlib import Path

from conftest import START, START_MS, FakeExchange

from martex_quant.data import pull
from martex_quant.data.collectors.binance import BinanceCollector
from martex_quant.data.models import Interval
from martex_quant.data.processors.validation import validate_ohlcv
from martex_quant.data.store.catalog import Catalog
from martex_quant.data.store.parquet_store import ParquetStore


def test_floor_to_interval() -> None:
    dt = datetime(2024, 6, 1, 13, 47, 12, tzinfo=UTC)
    assert pull.floor_to_interval(dt, Interval.H1) == datetime(2024, 6, 1, 13, tzinfo=UTC)
    assert pull.floor_to_interval(dt, Interval.D1) == datetime(2024, 6, 1, tzinfo=UTC)
    assert pull.floor_to_interval(dt, Interval.M15) == datetime(2024, 6, 1, 13, 45, tzinfo=UTC)


def test_collect_validate_store_roundtrip(tmp_path: Path) -> None:
    """The full pipeline, wired exactly as pull.run wires it, minus the network."""
    fake = FakeExchange(START_MS, n_bars=500)
    collector = BinanceCollector(client=fake, backoff_base_s=0.0)
    end = datetime(2024, 1, 21, 20, tzinfo=UTC)  # 500h after START

    df = collector.fetch_ohlcv("BTCUSDT", Interval.H1, START, end)
    report = validate_ohlcv(df, Interval.H1, requested_start=START, requested_end=end)
    assert not report.has_errors

    store = ParquetStore(tmp_path)
    result = store.write(df, "BTCUSDT", Interval.H1)
    assert result.rows_total == 500

    report_path = store.dataset_dir("BTCUSDT", Interval.H1) / "quality_report.json"
    pull._write_report(store, "BTCUSDT", Interval.H1, report)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["n_rows"] == 500

    back = store.read("BTCUSDT", Interval.H1)
    assert back.equals(df)


def test_catalog_reflects_pull(tmp_path: Path) -> None:
    catalog = Catalog(tmp_path)
    assert catalog.get("BTCUSDT", Interval.H1) is None  # empty before any pull
