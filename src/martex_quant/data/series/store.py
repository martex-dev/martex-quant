"""Canonical series store: one read path, with provenance and integrity.

Design constraints taken from the existing corpus rather than invented:

* **Timestamp semantics are preserved exactly, per kind.** Funding keys on
  ``timestamp``, perp on ``day``, intraday on ``ts``, streams on
  ``timestamp`` — and every one of them is microsecond UTC, because that is
  what the cache writers produced. The lake is millisecond. Neither is
  normalised here; the difference is recorded as a property of the kind and
  is the reason ``features.panel.align_day_to_cache_precision`` exists.
* **Frames come back unchanged.** ``read`` returns exactly what
  ``pl.read_parquet`` returned. Sorting, renaming and aggregation stay at the
  call sites, because those differ per study and are part of each published
  result.
* **Derived series declare their producer.** The equity streams under
  ``data/tmp/h4x_streams`` are computed artifacts consumed by eight scripts;
  recording which script produces them, and from what, is the only thing that
  makes them auditable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import polars as pl

_US_UTC = pl.Datetime(time_unit="us", time_zone="UTC")


class SeriesKind(StrEnum):
    FUNDING = "funding"  # Binance USDM funding rates, 8h cadence
    PERP = "perp"  # perpetual daily closes
    INTRADAY_15M = "intraday_15m"  # Bybit 15m OHLCV
    INTRADAY_TAKER = "intraday_taker"  # 15m close/volume/taker-buy
    INTRADAY_OI = "intraday_oi"  # 1h open interest
    # The derived cache holds TWO shapes under one naming convention — see
    # the finding in docs/research/mi-layer3-series-audit.md.
    EQUITY_STREAM = "equity_stream"  # DERIVED: timestamp/equity/exposure
    RETURN_STREAM = "return_stream"  # DERIVED: timestamp/ret


@dataclass(frozen=True)
class SeriesSpec:
    """Everything needed to locate, validate and explain one series kind."""

    kind: SeriesKind
    directory: str
    filename_template: str  # formatted with the series key
    time_column: str
    schema: dict[str, pl.DataType]
    derived: bool = False
    producer: str = ""  # for derived kinds: what script writes it
    upstream: tuple[str, ...] = ()  # for derived kinds: what it is computed from
    description: str = ""

    def path(self, root: Path, key: str) -> Path:
        return root / self.directory / self.filename_template.format(key=key)


SPECS: dict[SeriesKind, SeriesSpec] = {
    SeriesKind.FUNDING: SeriesSpec(
        kind=SeriesKind.FUNDING,
        directory="data/funding",
        filename_template="{key}.parquet",
        time_column="timestamp",
        schema={"timestamp": _US_UTC, "rate": pl.Float64()},
        description="Binance USDM funding-rate history, cached by h08's fetch_funding.",
    ),
    SeriesKind.PERP: SeriesSpec(
        kind=SeriesKind.PERP,
        directory="data/perp",
        filename_template="{key}.parquet",
        time_column="day",
        schema={"day": _US_UTC, "perp_close": pl.Float64()},
        description="Perpetual daily closes, cached by h10's fetch_perp_daily.",
    ),
    SeriesKind.INTRADAY_15M: SeriesSpec(
        kind=SeriesKind.INTRADAY_15M,
        directory="data/intraday",
        filename_template="{key}_15m.parquet",
        time_column="ts",
        schema={
            "ts": _US_UTC,
            "open": pl.Float64(),
            "high": pl.Float64(),
            "low": pl.Float64(),
            "close": pl.Float64(),
            "volume": pl.Float64(),
        },
        description="Bybit USDT-perp 15m OHLCV, 2021+, pulled by scripts/pull_intraday.py.",
    ),
    SeriesKind.INTRADAY_TAKER: SeriesSpec(
        kind=SeriesKind.INTRADAY_TAKER,
        directory="data/intraday",
        filename_template="{key}_tb15m.parquet",
        time_column="ts",
        schema={
            "ts": _US_UTC,
            "close": pl.Float64(),
            "volume": pl.Float64(),
            "taker_buy": pl.Float64(),
        },
        description="Binance USDM 15m with taker-buy volume; the H53 aggressor-flow input.",
    ),
    SeriesKind.INTRADAY_OI: SeriesSpec(
        kind=SeriesKind.INTRADAY_OI,
        directory="data/intraday",
        filename_template="{key}_oi1h.parquet",
        time_column="ts",
        schema={"ts": _US_UTC, "oi": pl.Float64()},
        description="Bybit 1h open interest. H54 is DATA-BLOCKED on this: ~200h only.",
    ),
    SeriesKind.EQUITY_STREAM: SeriesSpec(
        kind=SeriesKind.EQUITY_STREAM,
        directory="data/tmp/h4x_streams",
        filename_template="{key}.parquet",
        time_column="timestamp",
        schema={"timestamp": _US_UTC, "equity": pl.Float64(), "exposure": pl.Float64()},
        derived=True,
        producer="scripts/h41_h42_fub1_studies.py",
        upstream=("data/lake (1d OHLCV)", "config/universe.json"),
        description=(
            "Strategy equity curves (rot_stop_stream, rot_champion_stream). "
            "DERIVED and cached: consumed by h43, h51, h52_55_57 and the four "
            "sprint studies, but recomputed only if the cache is absent. "
            "Nothing verifies a recomputed stream matches the one those "
            "consumers were validated against."
        ),
    ),
    SeriesKind.RETURN_STREAM: SeriesSpec(
        kind=SeriesKind.RETURN_STREAM,
        directory="data/tmp/h4x_streams",
        filename_template="{key}.parquet",
        time_column="timestamp",
        schema={"timestamp": _US_UTC, "ret": pl.Float64()},
        derived=True,
        producer="scripts/h41_h42_fub1_studies.py",
        upstream=("data/lake (1d OHLCV)", "config/universe.json"),
        description=(
            "Per-period RETURN streams (v1_stream, v1_stop_stream, "
            "blend_stream). Same directory and naming convention as the equity "
            "streams but a different schema — a consumer expecting 'equity' "
            "gets a ColumnNotFound, and one that reads either without checking "
            "would be comparing a level against a return."
        ),
    ),
}

# Which concrete cache files carry which shape. Recorded because the file
# names do not distinguish them.
STREAM_KINDS: dict[str, SeriesKind] = {
    "rot_stop_stream": SeriesKind.EQUITY_STREAM,
    "rot_champion_stream": SeriesKind.EQUITY_STREAM,
    "v1_stream": SeriesKind.RETURN_STREAM,
    "v1_stop_stream": SeriesKind.RETURN_STREAM,
    "blend_stream": SeriesKind.RETURN_STREAM,
}


class SeriesIntegrityError(Exception):
    """Raised when a series cannot be trusted. Never downgraded to a warning:
    a silently-wrong input is how a research corpus rots."""


@dataclass(frozen=True)
class Provenance:
    """Where a frame came from and what it contained when it was read."""

    kind: SeriesKind
    key: str
    path: str
    sha256: str
    size_bytes: int
    rows: int
    schema: dict[str, str]
    time_column: str
    first_timestamp: str | None
    last_timestamp: str | None
    read_at: str
    derived: bool
    producer: str
    upstream: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "key": self.key,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "rows": self.rows,
            "schema": self.schema,
            "time_column": self.time_column,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "read_at": self.read_at,
            "derived": self.derived,
            "producer": self.producer,
            "upstream": list(self.upstream),
        }


@dataclass(frozen=True)
class SeriesRead:
    """A frame plus the provenance of the file it came from."""

    frame: pl.DataFrame
    provenance: Provenance


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SeriesStore:
    """Read non-OHLCV series with integrity checks and provenance.

    ``strict=True`` (the default) raises on any integrity failure. The
    research scripts run strict; a diagnostic caller can pass ``strict=False``
    to inspect a broken series via ``describe`` without tripping.
    """

    def __init__(self, root: Path, *, strict: bool = True) -> None:
        self.root = root
        self.strict = strict

    def spec(self, kind: SeriesKind) -> SeriesSpec:
        return SPECS[kind]

    def path(self, kind: SeriesKind, key: str) -> Path:
        return SPECS[kind].path(self.root, key)

    def exists(self, kind: SeriesKind, key: str) -> bool:
        return self.path(kind, key).exists()

    def read(self, kind: SeriesKind, key: str) -> pl.DataFrame:
        """The frame, byte-identical to what a direct ``pl.read_parquet`` gave.

        No sorting, renaming or aggregation: those differ per study and are
        part of each published result.
        """
        return self.read_with_provenance(kind, key).frame

    def read_with_provenance(self, kind: SeriesKind, key: str) -> SeriesRead:
        spec = SPECS[kind]
        path = spec.path(self.root, key)
        if not path.exists():
            raise SeriesIntegrityError(
                f"{kind.value} series '{key}' is missing at {path}. "
                + (
                    f"It is DERIVED — run {spec.producer} to regenerate it."
                    if spec.derived
                    else "It is a cached download; re-pull it before relying on this result."
                )
            )
        frame = pl.read_parquet(path)
        problems = check_integrity(frame, spec)
        if problems and self.strict:
            raise SeriesIntegrityError(
                f"{kind.value} series '{key}' failed integrity checks:\n  " + "\n  ".join(problems)
            )
        return SeriesRead(frame=frame, provenance=self._provenance(spec, key, path, frame))

    def describe(self, kind: SeriesKind, key: str) -> Provenance:
        """Provenance without trusting the contents — for audit and manifests."""
        spec = SPECS[kind]
        path = spec.path(self.root, key)
        if not path.exists():
            raise SeriesIntegrityError(f"{kind.value} series '{key}' is missing at {path}")
        return self._provenance(spec, key, path, pl.read_parquet(path))

    def manifest(self, requested: dict[SeriesKind, list[str]]) -> dict[str, Any]:
        """Provenance for a set of series, as a JSON-safe audit record.

        This is what makes a research run reproducible after the fact: the
        hashes here identify exactly which bytes produced a result, and
        ``/data/`` is gitignored so nothing else records them.
        """
        entries = [
            self.describe(kind, key).to_dict()
            for kind, keys in requested.items()
            for key in sorted(keys)
        ]
        # read_at is when we looked, not what we looked at. Excluding it makes
        # the digest an identity of the DATA, so two runs over unchanged files
        # produce the same manifest hash.
        identity = [{k: v for k, v in e.items() if k != "read_at"} for e in entries]
        payload = json.dumps(identity, sort_keys=True).encode("utf-8")
        return {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "series": entries,
            "manifest_sha256": hashlib.sha256(payload).hexdigest(),
        }

    def _provenance(
        self, spec: SeriesSpec, key: str, path: Path, frame: pl.DataFrame
    ) -> Provenance:
        column = spec.time_column
        has_time = column in frame.columns and frame.height > 0
        return Provenance(
            kind=spec.kind,
            key=key,
            path=str(path.relative_to(self.root).as_posix()),
            sha256=_sha256(path),
            size_bytes=path.stat().st_size,
            rows=frame.height,
            schema={name: str(dtype) for name, dtype in frame.schema.items()},
            time_column=column,
            first_timestamp=str(frame[column][0]) if has_time else None,
            last_timestamp=str(frame[column][-1]) if has_time else None,
            read_at=datetime.now(tz=UTC).isoformat(),
            derived=spec.derived,
            producer=spec.producer,
            upstream=spec.upstream,
        )


def check_integrity(frame: pl.DataFrame, spec: SeriesSpec) -> list[str]:
    """Every way a series can be untrustworthy, as human-readable problems.

    Detects: empty data, schema drift (missing columns, extra columns, dtype
    changes — including a timestamp precision change, which would silently
    empty a join), a missing time column, unsorted timestamps, and duplicate
    timestamps.

    Deliberately NOT checked: gaps. The intraday caches legitimately contain
    exchange-downtime holes and young listings, and the lake's own validator
    already treats gaps as a warning rather than an error.
    """
    problems: list[str] = []
    actual = dict(frame.schema)

    for name, dtype in spec.schema.items():
        if name not in actual:
            problems.append(f"missing column '{name}'")
        elif actual[name] != dtype:
            problems.append(f"column '{name}' has dtype {actual[name]}, expected {dtype}")
    for name in actual:
        if name not in spec.schema:
            problems.append(f"unexpected column '{name}' (schema drift)")

    if frame.height == 0:
        problems.append("series is empty")
        return problems

    column = spec.time_column
    if column not in actual:
        return problems  # already reported; the checks below would be noise

    series = frame[column]
    if not series.is_sorted():
        problems.append(f"'{column}' is not sorted ascending")
    duplicates = series.len() - series.n_unique()
    if duplicates:
        problems.append(f"{duplicates} duplicate '{column}' value(s)")
    return problems


def staleness_days(provenance: Provenance, *, now: datetime | None = None) -> float | None:
    """Age of the newest observation, in days. None when the series is empty.

    Staleness is reported rather than enforced: what counts as stale is a
    per-study decision — the intraday caches are deliberately frozen at 2026,
    while a live paper run would want data from yesterday.
    """
    if provenance.last_timestamp is None:
        return None
    last = datetime.fromisoformat(provenance.last_timestamp)
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    reference = now if now is not None else datetime.now(tz=UTC)
    return (reference - last).total_seconds() / 86_400.0
