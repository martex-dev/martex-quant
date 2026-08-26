"""Parquet data lake, hive-partitioned by symbol / interval / year.

Layout::

    <root>/ohlcv/symbol=BTCUSDT/interval=1h/year=2024/data.parquet

Writes are idempotent upserts: re-pulling a range merges with existing data
(new rows win on timestamp collisions) and each year file is replaced
atomically (write temp, then rename), so a crash can never leave a
half-written dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from martex_quant.data.models import OHLCV_SCHEMA, Interval

_DATA_FILE = "data.parquet"


@dataclass(frozen=True)
class WriteResult:
    rows_total: int
    years_written: list[int]


class ParquetStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def dataset_dir(self, symbol: str, interval: Interval) -> Path:
        return self.root / "ohlcv" / f"symbol={symbol}" / f"interval={interval}"

    def write(self, df: pl.DataFrame, symbol: str, interval: Interval) -> WriteResult:
        """Upsert a canonical OHLCV frame into the lake."""
        if dict(df.schema) != OHLCV_SCHEMA:
            raise ValueError(f"frame does not match canonical OHLCV schema: {dict(df.schema)}")
        if df.height == 0:
            return WriteResult(rows_total=0, years_written=[])

        df = df.sort("timestamp").unique(subset="timestamp", keep="last", maintain_order=True)
        years_written: list[int] = []
        rows_total = 0

        for (year,), year_df in df.group_by(
            pl.col("timestamp").dt.year().alias("year"), maintain_order=True
        ):
            assert isinstance(year, int)
            part_dir = self.dataset_dir(symbol, interval) / f"year={year}"
            part_dir.mkdir(parents=True, exist_ok=True)
            target = part_dir / _DATA_FILE

            merged = year_df
            if target.exists():
                existing = pl.read_parquet(target)
                merged = (
                    pl.concat([existing, year_df])
                    .sort("timestamp")
                    # keep="last" -> freshly pulled rows win over stored ones
                    .unique(subset="timestamp", keep="last", maintain_order=True)
                )

            tmp = part_dir / f"{_DATA_FILE}.tmp"
            merged.write_parquet(tmp)
            tmp.replace(target)  # atomic on the same filesystem

            years_written.append(year)
            rows_total += merged.height

        return WriteResult(rows_total=rows_total, years_written=sorted(years_written))

    def read(
        self,
        symbol: str,
        interval: Interval,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pl.DataFrame:
        """Read a dataset, optionally sliced to [start, end)."""
        files = sorted(self.dataset_dir(symbol, interval).glob(f"year=*/{_DATA_FILE}"))
        if not files:
            raise FileNotFoundError(f"no data stored for {symbol} {interval} under {self.root}")
        lf = pl.scan_parquet(files)
        if start is not None:
            lf = lf.filter(pl.col("timestamp") >= start)
        if end is not None:
            lf = lf.filter(pl.col("timestamp") < end)
        return lf.sort("timestamp").collect()
