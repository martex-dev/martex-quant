"""Series store: provenance, integrity, cache identity and reproducibility.

The migration equivalence test comes first — the store must hand back exactly
what a direct ``pl.read_parquet`` handed back, or every published result that
depends on these files changes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from trading_bot.data.series.store import (
    SPECS,
    STREAM_KINDS,
    Provenance,
    SeriesIntegrityError,
    SeriesKind,
    SeriesStore,
    check_integrity,
    staleness_days,
)

_US_UTC = pl.Datetime(time_unit="us", time_zone="UTC")


def _write(path: Path, frame: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)


def _funding(n: int = 50, *, start: datetime | None = None) -> pl.DataFrame:
    origin = start or datetime(2024, 1, 1, tzinfo=UTC)
    return pl.DataFrame(
        {
            "timestamp": [origin + timedelta(hours=8 * i) for i in range(n)],
            "rate": [0.0001 * i for i in range(n)],
        },
        schema={"timestamp": _US_UTC, "rate": pl.Float64()},
    )


@pytest.fixture
def store(tmp_path: Path) -> SeriesStore:
    _write(tmp_path / "data" / "funding" / "BTCUSDT.parquet", _funding())
    _write(
        tmp_path / "data" / "tmp" / "h4x_streams" / "rot_stop_stream.parquet",
        pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(20)
                ],
                "equity": [10_000.0 + 10 * i for i in range(20)],
                "exposure": [0.5] * 20,
            },
            schema={"timestamp": _US_UTC, "equity": pl.Float64(), "exposure": pl.Float64()},
        ),
    )
    return SeriesStore(tmp_path)


# --- equivalence: the store must not change any frame --------------------


def test_read_is_byte_identical_to_a_direct_read(store: SeriesStore) -> None:
    """The migration guarantee. If this fails, published results move."""
    direct = pl.read_parquet(store.path(SeriesKind.FUNDING, "BTCUSDT"))
    assert store.read(SeriesKind.FUNDING, "BTCUSDT").equals(direct)


def test_read_does_not_sort_rename_or_aggregate(store: SeriesStore) -> None:
    """Those transformations differ per study and are part of each result."""
    frame = store.read(SeriesKind.FUNDING, "BTCUSDT")
    assert frame.columns == ["timestamp", "rate"]
    assert frame.height == 50


# --- provenance ----------------------------------------------------------


def test_provenance_records_identity_schema_and_span(store: SeriesStore) -> None:
    read = store.read_with_provenance(SeriesKind.FUNDING, "BTCUSDT")
    p = read.provenance
    assert p.kind is SeriesKind.FUNDING
    assert p.key == "BTCUSDT"
    assert p.path == "data/funding/BTCUSDT.parquet"
    assert len(p.sha256) == 64
    assert p.rows == 50
    assert p.schema == {"timestamp": "Datetime(time_unit='us', time_zone='UTC')", "rate": "Float64"}
    assert p.time_column == "timestamp"
    assert p.first_timestamp is not None and p.last_timestamp is not None
    assert not p.derived


def test_derived_series_declare_producer_and_upstream(store: SeriesStore) -> None:
    """Cache provenance: the equity streams are computed artifacts that eight
    scripts consume as inputs."""
    p = store.describe(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
    assert p.derived
    assert p.producer == "scripts/h41_h42_fub1_studies.py"
    assert "data/lake (1d OHLCV)" in p.upstream
    assert "config/universe.json" in p.upstream


def test_cache_identity_changes_when_bytes_change(store: SeriesStore, tmp_path: Path) -> None:
    before = store.describe(SeriesKind.FUNDING, "BTCUSDT").sha256
    _write(tmp_path / "data" / "funding" / "BTCUSDT.parquet", _funding(51))
    after = store.describe(SeriesKind.FUNDING, "BTCUSDT")
    assert after.sha256 != before
    assert after.rows == 51


def test_manifest_is_stable_and_self_hashing(store: SeriesStore) -> None:
    request = {SeriesKind.FUNDING: ["BTCUSDT"], SeriesKind.EQUITY_STREAM: ["rot_stop_stream"]}
    first, second = store.manifest(request), store.manifest(request)
    assert first["manifest_sha256"] == second["manifest_sha256"]  # read_at excluded
    assert len(first["series"]) == 2


# --- integrity -----------------------------------------------------------


def test_missing_series_raises_with_an_actionable_message(store: SeriesStore) -> None:
    with pytest.raises(SeriesIntegrityError, match="re-pull it"):
        store.read(SeriesKind.FUNDING, "NOPEUSDT")
    with pytest.raises(SeriesIntegrityError, match="h41_h42_fub1_studies"):
        store.read(SeriesKind.EQUITY_STREAM, "absent_stream")


def test_schema_drift_is_detected(store: SeriesStore, tmp_path: Path) -> None:
    _write(
        tmp_path / "data" / "funding" / "BTCUSDT.parquet",
        _funding().rename({"rate": "funding_rate"}),
    )
    with pytest.raises(SeriesIntegrityError, match="missing column 'rate'"):
        store.read(SeriesKind.FUNDING, "BTCUSDT")


def test_timestamp_precision_change_is_detected(store: SeriesStore, tmp_path: Path) -> None:
    """A us->ms drift would silently empty every join against the lake, which
    is exactly the provenance hazard recorded as correction candidate 4."""
    ms = _funding().with_columns(pl.col("timestamp").cast(pl.Datetime("ms", "UTC")))
    _write(tmp_path / "data" / "funding" / "BTCUSDT.parquet", ms)
    with pytest.raises(SeriesIntegrityError, match="dtype"):
        store.read(SeriesKind.FUNDING, "BTCUSDT")


def test_unsorted_and_duplicate_timestamps_are_detected() -> None:
    spec = SPECS[SeriesKind.FUNDING]
    shuffled = _funding(10).sample(fraction=1.0, shuffle=True, seed=3)
    assert any("not sorted" in p for p in check_integrity(shuffled, spec))
    duplicated = pl.concat([_funding(3), _funding(3)]).sort("timestamp")
    assert any("duplicate" in p for p in check_integrity(duplicated, spec))


def test_empty_series_is_detected() -> None:
    spec = SPECS[SeriesKind.FUNDING]
    empty = pl.DataFrame(schema={"timestamp": _US_UTC, "rate": pl.Float64()})
    assert "series is empty" in check_integrity(empty, spec)


def test_non_strict_mode_reports_without_raising(tmp_path: Path) -> None:
    _write(tmp_path / "data" / "funding" / "X.parquet", _funding().rename({"rate": "r"}))
    lenient = SeriesStore(tmp_path, strict=False)
    assert lenient.read(SeriesKind.FUNDING, "X").height == 50
    with pytest.raises(SeriesIntegrityError):
        SeriesStore(tmp_path).read(SeriesKind.FUNDING, "X")


# --- timestamp semantics -------------------------------------------------


def test_every_kind_declares_microsecond_utc_and_its_own_time_column() -> None:
    """Preserved, not normalised: the caches are us while the lake is ms, and
    each kind keys on a different column name."""
    expected = {
        SeriesKind.FUNDING: "timestamp",
        SeriesKind.PERP: "day",
        SeriesKind.INTRADAY_15M: "ts",
        SeriesKind.INTRADAY_TAKER: "ts",
        SeriesKind.INTRADAY_OI: "ts",
        SeriesKind.EQUITY_STREAM: "timestamp",
    }
    for kind, column in expected.items():
        spec = SPECS[kind]
        assert spec.time_column == column
        assert spec.schema[column] == _US_UTC


# --- staleness -----------------------------------------------------------


def test_staleness_is_reported_not_enforced(store: SeriesStore) -> None:
    p = store.describe(SeriesKind.FUNDING, "BTCUSDT")
    age = staleness_days(p, now=datetime(2024, 3, 1, tzinfo=UTC))
    assert age is not None and age > 40
    empty = Provenance(
        kind=SeriesKind.FUNDING,
        key="k",
        path="p",
        sha256="s",
        size_bytes=0,
        rows=0,
        schema={},
        time_column="timestamp",
        first_timestamp=None,
        last_timestamp=None,
        read_at="",
        derived=False,
        producer="",
        upstream=(),
    )
    assert staleness_days(empty) is None


# --- reproducibility -----------------------------------------------------


def test_repeated_reads_are_identical(store: SeriesStore) -> None:
    a = store.read_with_provenance(SeriesKind.FUNDING, "BTCUSDT")
    b = store.read_with_provenance(SeriesKind.FUNDING, "BTCUSDT")
    assert a.frame.equals(b.frame)
    assert a.provenance.sha256 == b.provenance.sha256
    assert a.provenance.rows == b.provenance.rows


def test_the_derived_cache_holds_two_shapes_under_one_convention() -> None:
    """Layer 3 finding: data/tmp/h4x_streams mixes equity curves
    (timestamp/equity/exposure) and return series (timestamp/ret) with
    indistinguishable file names. STREAM_KINDS records which is which so a
    consumer cannot read a return series expecting a level."""
    assert STREAM_KINDS["rot_stop_stream"] is SeriesKind.EQUITY_STREAM
    assert STREAM_KINDS["v1_stream"] is SeriesKind.RETURN_STREAM
    equity = SPECS[SeriesKind.EQUITY_STREAM].schema
    returns = SPECS[SeriesKind.RETURN_STREAM].schema
    assert "equity" in equity and "equity" not in returns
    assert "ret" in returns and "ret" not in equity
    assert SPECS[SeriesKind.EQUITY_STREAM].directory == SPECS[SeriesKind.RETURN_STREAM].directory


def test_reading_a_return_stream_as_an_equity_stream_is_caught(tmp_path: Path) -> None:
    frame = pl.DataFrame(
        {"timestamp": [datetime(2024, 1, 1, tzinfo=UTC)], "ret": [0.01]},
        schema={"timestamp": _US_UTC, "ret": pl.Float64()},
    )
    _write(tmp_path / "data" / "tmp" / "h4x_streams" / "v1_stream.parquet", frame)
    store = SeriesStore(tmp_path)
    with pytest.raises(SeriesIntegrityError, match="missing column 'equity'"):
        store.read(SeriesKind.EQUITY_STREAM, "v1_stream")
    assert store.read(SeriesKind.RETURN_STREAM, "v1_stream").columns == ["timestamp", "ret"]
