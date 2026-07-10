"""Milestone 1 deliverable::

    python -m trading_bot.data.pull --symbol BTCUSDT --interval 1h --years 4

Collect -> validate -> report -> store. Data with ERROR-severity findings is
never written to the lake; the process exits nonzero so scripts can react.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_bot.data.collectors.binance import BinanceCollector
from trading_bot.data.models import Interval
from trading_bot.data.processors.validation import ValidationReport, validate_ohlcv
from trading_bot.data.store.catalog import Catalog, DatasetEntry
from trading_bot.data.store.parquet_store import ParquetStore

logger = logging.getLogger(__name__)

_REPORT_FILE = "quality_report.json"


def floor_to_interval(dt: datetime, interval: Interval) -> datetime:
    """Floor a datetime to the interval grid (grid is epoch-aligned, UTC)."""
    ms = int(dt.timestamp() * 1000)
    floored = (ms // interval.milliseconds) * interval.milliseconds
    return datetime.fromtimestamp(floored / 1000, tz=UTC)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m trading_bot.data.pull",
        description="Pull, validate, and store OHLCV history from Binance.",
    )
    parser.add_argument("--symbol", required=True, help="e.g. BTCUSDT")
    parser.add_argument(
        "--interval", required=True, choices=[i.value for i in Interval], help="bar interval"
    )
    parser.add_argument("--years", type=float, default=4.0, help="lookback from now (default: 4)")
    parser.add_argument(
        "--lake", type=Path, default=Path("data/lake"), help="lake root (default: data/lake)"
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    interval = Interval(args.interval)

    # End at the last complete bar: the in-progress bar is excluded because
    # its close/high/low are still changing.
    end = floor_to_interval(datetime.now(tz=UTC), interval)
    start = end - timedelta(days=365.25 * args.years)
    logger.info("pulling %s %s from %s to %s", args.symbol, interval, start, end)

    collector = BinanceCollector()
    df = collector.fetch_ohlcv(args.symbol, interval, start, end)
    logger.info("fetched %d bars", df.height)

    report = validate_ohlcv(df, interval, requested_start=start, requested_end=end)
    print(report.to_text())

    if report.has_errors:
        logger.error("validation failed with errors — nothing written to the lake")
        return 1

    store = ParquetStore(args.lake)
    result = store.write(df, args.symbol, interval)
    _write_report(store, args.symbol, interval, report)

    first_ts = df["timestamp"].min()
    last_ts = df["timestamp"].max()
    assert isinstance(first_ts, datetime) and isinstance(last_ts, datetime)
    Catalog(args.lake).update(
        DatasetEntry(
            symbol=args.symbol,
            interval=interval,
            rows=result.rows_total,
            start=first_ts,
            end=last_ts,
            updated_at=datetime.now(tz=UTC),
            validation_errors=report.n_errors,
            validation_warnings=report.n_warnings,
        )
    )
    logger.info(
        "stored %d rows across years %s under %s",
        result.rows_total,
        result.years_written,
        store.dataset_dir(args.symbol, interval),
    )
    return 0


def _write_report(
    store: ParquetStore, symbol: str, interval: Interval, report: ValidationReport
) -> None:
    path = store.dataset_dir(symbol, interval) / _REPORT_FILE
    path.write_text(json.dumps(json.loads(report.model_dump_json()), indent=2), encoding="utf-8")
    logger.info("quality report written to %s", path)


if __name__ == "__main__":
    sys.exit(run())
