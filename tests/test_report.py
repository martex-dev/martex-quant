"""Report command tests: formatting, completeness math, exit codes."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from trading_bot.data import report
from trading_bot.data.models import Interval
from trading_bot.data.store.catalog import Catalog, DatasetEntry


def make_entry(symbol: str = "BTCUSDT", rows: int = 25, errors: int = 0) -> DatasetEntry:
    # 25 hourly bars = a complete [00:00 .. 00:00 next day] inclusive grid.
    return DatasetEntry(
        symbol=symbol,
        interval=Interval.H1,
        rows=rows,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 2, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 1, tzinfo=UTC),
        validation_errors=errors,
        validation_warnings=1,
    )


def test_completeness_full_grid() -> None:
    assert report.completeness_pct(make_entry(rows=25)) == pytest.approx(100.0)


def test_completeness_partial_grid() -> None:
    assert report.completeness_pct(make_entry(rows=20)) == pytest.approx(80.0)


def test_report_lists_datasets_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = Catalog(tmp_path)
    catalog.update(make_entry("BTCUSDT"))
    catalog.update(make_entry("ETHUSDT"))

    assert report.run(["--lake", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "BTCUSDT/1h" in out
    assert "ETHUSDT/1h" in out
    assert "2 dataset(s), 0 with validation errors" in out


def test_report_exits_nonzero_on_errors(tmp_path: Path) -> None:
    Catalog(tmp_path).update(make_entry(errors=2))
    assert report.run(["--lake", str(tmp_path)]) == 1


def test_report_empty_catalog_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert report.run(["--lake", str(tmp_path)]) == 1
    assert "empty" in capsys.readouterr().out
