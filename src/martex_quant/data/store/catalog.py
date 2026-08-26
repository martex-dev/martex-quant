"""Dataset catalog: a JSON registry of what the lake contains.

One entry per (symbol, interval): row count, time coverage, when it was last
updated, and the outcome of its last validation. The catalog is the answer to
"what data do we have and can we trust it" without scanning Parquet files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from martex_quant.data.models import Interval

_CATALOG_FILE = "catalog.json"


class DatasetEntry(BaseModel):
    symbol: str
    interval: Interval
    rows: int
    start: datetime
    end: datetime
    updated_at: datetime
    validation_errors: int
    validation_warnings: int

    @property
    def key(self) -> str:
        return f"{self.symbol}/{self.interval}"


class Catalog:
    def __init__(self, root: Path) -> None:
        self.path = root / _CATALOG_FILE
        self._entries: dict[str, DatasetEntry] = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._entries = {k: DatasetEntry.model_validate(v) for k, v in raw.items()}

    def update(self, entry: DatasetEntry) -> None:
        self._entries[entry.key] = entry
        self._save()

    def get(self, symbol: str, interval: Interval) -> DatasetEntry | None:
        return self._entries.get(f"{symbol}/{interval}")

    def entries(self) -> list[DatasetEntry]:
        return sorted(self._entries.values(), key=lambda e: e.key)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: json.loads(v.model_dump_json()) for k, v in self._entries.items()}
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
