"""Data-quality report across the whole lake::

    python -m martex_quant.data.report

Summarizes every dataset in the catalog: coverage, completeness against the
interval grid, and validation outcome. Exits nonzero if any dataset carries
validation errors, so it can gate automated jobs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from martex_quant.data.store.catalog import Catalog, DatasetEntry


def completeness_pct(entry: DatasetEntry) -> float:
    """Actual rows as a percentage of the full interval grid over [start, end]."""
    expected = (
        int((entry.end - entry.start).total_seconds() * 1000) // entry.interval.milliseconds + 1
    )
    return 100.0 * entry.rows / expected if expected > 0 else 0.0


def format_report(entries: list[DatasetEntry]) -> str:
    header = (
        f"{'dataset':<16} {'rows':>8} {'from':<12} {'to':<12} "
        f"{'complete':>9} {'errors':>7} {'warnings':>9}"
    )
    lines = [header, "-" * len(header)]
    for e in entries:
        lines.append(
            f"{e.key:<16} {e.rows:>8} {e.start:%Y-%m-%d}   {e.end:%Y-%m-%d}   "
            f"{completeness_pct(e):>8.2f}% {e.validation_errors:>7} {e.validation_warnings:>9}"
        )
    n_bad = sum(e.validation_errors > 0 for e in entries)
    lines.append(f"\n{len(entries)} dataset(s), {n_bad} with validation errors")
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m martex_quant.data.report",
        description="Summarize data quality for every dataset in the lake.",
    )
    parser.add_argument(
        "--lake", type=Path, default=Path("data/lake"), help="lake root (default: data/lake)"
    )
    args = parser.parse_args(argv)

    entries = Catalog(args.lake).entries()
    if not entries:
        print(f"catalog at {args.lake} is empty — nothing has been pulled yet")
        return 1
    print(format_report(entries))
    return 1 if any(e.validation_errors > 0 for e in entries) else 0


if __name__ == "__main__":
    sys.exit(run())
