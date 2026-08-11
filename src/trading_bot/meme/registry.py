"""Append-only registry of observed token launches.

The point of this file is bias control, and it is worth being explicit about
why it has to exist at all.

Every "browse" endpoint any of these APIs offers — top pools by volume, trending
tokens, boosted profiles — is a list of *survivors*. Building a dataset from
one and then discovering that new tokens tend to do well is not a finding; it is
the sampling frame talking. The only clean cohort is one where membership is
decided at birth, before any outcome exists, and never revised.

So: we poll the new-pool stream, write down every pool the first time we see it
along with its state at that moment, and never touch that row again. Outcomes
get measured later, in a separate file, keyed by pool address. A token that dies
in nine minutes stays in the registry with exactly the same standing as one that
runs 100x. That property is the dataset's entire value.

Storage is newline-delimited JSON partitioned by UTC discovery date: appendable
without a rewrite, readable by polars, and survives a crash mid-write with at
worst one truncated final line.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_bot.meme.sources.geckoterminal import PoolSnapshot

logger = logging.getLogger(__name__)

DEFAULT_ROOT = Path("data/meme/launches")


class LaunchRegistry:
    """First-sighting store for pools, partitioned by UTC date."""

    def __init__(self, root: Path | str = DEFAULT_ROOT, *, dedup_days: int = 3) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._dedup_days = dedup_days
        self._seen: set[str] = set()
        self._load_recent_addresses()

    @property
    def root(self) -> Path:
        return self._root

    def _partition_path(self, when: datetime) -> Path:
        return self._root / f"{when.astimezone(UTC):%Y-%m-%d}.jsonl"

    def _load_recent_addresses(self) -> None:
        """Seed the dedup set from the last few partitions.

        Bounded on purpose: a pool first seen a week ago cannot reappear in a
        five-minute-wide new-pool window, so scanning the whole history to
        prove it would be wasted I/O that grows without limit.
        """
        today = datetime.now(UTC)
        for offset in range(self._dedup_days):
            path = self._partition_path(today - timedelta(days=offset))
            if not path.exists():
                continue
            for row in _read_jsonl(path):
                address = row.get("pool_address")
                if isinstance(address, str):
                    self._seen.add(address)
        logger.info("registry seeded with %d known pools", len(self._seen))

    def __len__(self) -> int:
        return len(self._seen)

    def register(self, snapshots: Iterable[PoolSnapshot]) -> list[PoolSnapshot]:
        """Persist every snapshot whose pool we have not recorded before.

        Returns the ones actually written, so a caller can report discovery
        rate without re-reading the file.
        """
        fresh = [
            snap for snap in snapshots if snap.pool_address and snap.pool_address not in self._seen
        ]
        if not fresh:
            return []

        # Partition by the discovery timestamp so a run spanning UTC midnight
        # splits cleanly instead of landing yesterday's file.
        by_path: dict[Path, list[PoolSnapshot]] = {}
        for snap in fresh:
            by_path.setdefault(self._partition_path(snap.observed_at), []).append(snap)

        for path, batch in by_path.items():
            with path.open("a", encoding="utf-8") as handle:
                for snap in batch:
                    handle.write(json.dumps(snap.to_row(), separators=(",", ":")) + "\n")

        for snap in fresh:
            self._seen.add(snap.pool_address)
        return fresh

    def iter_rows(self, *, since: datetime | None = None) -> Iterator[dict[str, Any]]:
        """Yield registry rows in partition order, optionally filtered by date."""
        for path in sorted(self._root.glob("*.jsonl")):
            if since is not None:
                try:
                    day = datetime.strptime(path.stem, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    continue
                if day < since - timedelta(days=1):
                    continue
            yield from _read_jsonl(path)


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Read a JSONL file, skipping a truncated final line rather than dying."""
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skipping malformed line %d in %s", line_no, path)
                continue
            yield row
