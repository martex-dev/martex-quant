"""Refresh data/lake-current to the last complete daily bar.

    .venv/Scripts/python scripts/refresh_current_lake.py

PROJECT_STATE records the two-lake decision: `data/lake` is FROZEN at
2026-07-09 and is the witness for every published figure, while
`data/lake-current` is the moving store for new research and the H59
divergence hunt. This script touches ONLY the current lake.

**It cannot bump the research epoch and must never be made to.** Bumping
the epoch is a deliberate act -- re-verify every stdout golden against
the old lake, swap, re-freeze, record which published figures moved --
and is explicitly "not done by running a pull".

Full history is re-pulled rather than appended so the store is a complete
dataset rather than a patchwork of ranges, and `data.pull` refuses to
write anything carrying an ERROR-severity validation finding.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from martex_quant.data.models import Interval
from martex_quant.data.pull import run as pull_run
from martex_quant.data.store.parquet_store import ParquetStore

ROOT = Path(".")
FROZEN = ROOT / "data/lake"
CURRENT = ROOT / "data/lake-current"
YEARS = 9.2  # covers the lake's 2017-08-17 start with room to spare


def main() -> None:
    symbols: list[str] = json.loads((ROOT / "config/universe.json").read_text("utf-8"))["symbols"]
    print(f"refreshing {CURRENT} for {len(symbols)} symbols ({YEARS}y each)\n")

    failed: list[str] = []
    for i, symbol in enumerate(symbols, 1):
        code = pull_run(
            [
                "--symbol",
                symbol,
                "--interval",
                Interval.D1.value,
                "--years",
                str(YEARS),
                "--lake",
                str(CURRENT),
            ]
        )
        if code != 0:
            failed.append(symbol)
        print(f"  [{i:>2}/{len(symbols)}] {symbol:<12} {'OK' if code == 0 else 'FAILED'}")

    print("\n--- result ---")
    frozen_store, current_store = ParquetStore(FROZEN), ParquetStore(CURRENT)
    ends: list[str] = []
    for symbol in symbols:
        try:
            end = current_store.read(symbol, Interval.D1)["timestamp"].max()
        except Exception:
            continue
        ends.append(str(end)[:10])
    print(f"current lake ends: {sorted(set(ends))[-3:]}  ({len(ends)} symbols readable)")
    if failed:
        print(f"FAILED (not written): {', '.join(failed)}")

    # The frozen lake is the witness for every published number. Prove this
    # script did not touch it rather than asserting that it did not.
    frozen = frozen_store.read("BTCUSDT", Interval.D1)
    print(
        f"frozen lake UNCHANGED check: BTCUSDT n={frozen.height} "
        f"ends {str(frozen['timestamp'].max())[:10]} "
        f"(must still be 2026-07-09/10)"
    )
    overlap = (
        frozen.select("timestamp", pl.col("close").alias("frozen"))
        .join(
            current_store.read("BTCUSDT", Interval.D1).select(
                "timestamp", pl.col("close").alias("current")
            ),
            on="timestamp",
            how="inner",
        )
        .with_columns(diff=(pl.col("frozen") - pl.col("current")).abs())
    )
    print(
        f"frozen vs current on the {overlap.height} shared days: "
        f"max |diff| = {overlap['diff'].max():.10f}"
    )


if __name__ == "__main__":
    main()
