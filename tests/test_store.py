"""Store tests: roundtrip, partitioning, idempotent upsert, catalog."""

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from trading_bot.data.models import Interval, ohlcv_frame_from_rows
from trading_bot.data.store.catalog import Catalog, DatasetEntry
from trading_bot.data.store.parquet_store import ParquetStore

H1_MS = 3_600_000


def make_frame(start: datetime, n_bars: int, base_price: float = 100.0) -> pl.DataFrame:
    start_ms = int(start.timestamp() * 1000)
    rows = [
        [start_ms + i * H1_MS, base_price, base_price + 1, base_price - 1, base_price, 10.0 + i]
        for i in range(n_bars)
    ]
    return ohlcv_frame_from_rows(rows)


def test_write_read_roundtrip(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    df = make_frame(datetime(2024, 6, 1, tzinfo=UTC), 48)
    result = store.write(df, "BTCUSDT", Interval.H1)
    assert result.rows_total == 48
    assert result.years_written == [2024]

    back = store.read("BTCUSDT", Interval.H1)
    assert back.equals(df)


def test_year_boundary_creates_two_partitions(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    # 48 bars starting Dec 31 00:00 -> spans into Jan 1 of the next year.
    df = make_frame(datetime(2023, 12, 31, tzinfo=UTC), 48)
    result = store.write(df, "BTCUSDT", Interval.H1)
    assert result.years_written == [2023, 2024]

    dataset = store.dataset_dir("BTCUSDT", Interval.H1)
    assert (dataset / "year=2023" / "data.parquet").exists()
    assert (dataset / "year=2024" / "data.parquet").exists()
    assert store.read("BTCUSDT", Interval.H1).equals(df)


def test_rewrite_is_idempotent_and_new_rows_win(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    start = datetime(2024, 6, 1, tzinfo=UTC)
    store.write(make_frame(start, 24, base_price=100.0), "BTCUSDT", Interval.H1)
    # Overlapping re-pull with different prices: overlap must be replaced.
    store.write(make_frame(start, 24, base_price=200.0), "BTCUSDT", Interval.H1)

    back = store.read("BTCUSDT", Interval.H1)
    assert back.height == 24  # no duplicates
    assert back["close"].unique().to_list() == [200.0]


def test_read_with_time_slice(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    start = datetime(2024, 6, 1, tzinfo=UTC)
    store.write(make_frame(start, 100), "BTCUSDT", Interval.H1)

    sliced = store.read(
        "BTCUSDT",
        Interval.H1,
        start=datetime(2024, 6, 2, tzinfo=UTC),
        end=datetime(2024, 6, 3, tzinfo=UTC),
    )
    assert sliced.height == 24  # end is exclusive
    assert sliced["timestamp"].min() == datetime(2024, 6, 2, tzinfo=UTC)


def test_read_missing_dataset_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ParquetStore(tmp_path).read("NOPE", Interval.H1)


def test_write_rejects_wrong_schema(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="canonical"):
        ParquetStore(tmp_path).write(pl.DataFrame({"x": [1]}), "BTCUSDT", Interval.H1)


def test_catalog_roundtrip(tmp_path: Path) -> None:
    entry = DatasetEntry(
        symbol="BTCUSDT",
        interval=Interval.H1,
        rows=100,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        updated_at=datetime(2024, 1, 6, tzinfo=UTC),
        validation_errors=0,
        validation_warnings=2,
    )
    Catalog(tmp_path).update(entry)

    # A fresh instance must read the same state back from disk.
    reloaded = Catalog(tmp_path)
    got = reloaded.get("BTCUSDT", Interval.H1)
    assert got == entry
    assert reloaded.entries() == [entry]
    assert reloaded.get("ETHUSDT", Interval.H1) is None


def test_catalog_update_overwrites_same_key(tmp_path: Path) -> None:
    catalog = Catalog(tmp_path)
    base = dict(
        symbol="BTCUSDT",
        interval=Interval.H1,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        updated_at=datetime(2024, 1, 6, tzinfo=UTC),
        validation_errors=0,
        validation_warnings=0,
    )
    catalog.update(DatasetEntry(rows=100, **base))  # type: ignore[arg-type]
    catalog.update(DatasetEntry(rows=250, **base))  # type: ignore[arg-type]

    entry = Catalog(tmp_path).get("BTCUSDT", Interval.H1)
    assert entry is not None
    assert entry.rows == 250
    assert len(Catalog(tmp_path).entries()) == 1
