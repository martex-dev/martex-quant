"""Equivalence with the historical cross-sectional spread and 15m loader.

Each test embeds the historical code verbatim and asserts the canonical
implementation reproduces it exactly, before any caller is migrated.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from martex_quant.features.cross_section import ranking_spread_series
from martex_quant.features.intraday import load_15m_bars

MIN_COINS = 10


def _panel(n_days: int = 40, n_symbols: int = 14, seed: int = 5) -> pl.DataFrame:
    """A daily panel with ragged listing dates and scattered nulls — the two
    conditions that make null placement and the min-symbols gate bite."""
    rng = random.Random(seed)
    start = datetime(2021, 1, 1, tzinfo=UTC)
    rows = []
    for s in range(n_symbols):
        first = s * 2  # staggered listings -> some days have a thin cross-section
        for d in range(first, n_days):
            rows.append(
                {
                    "day": start + timedelta(days=d),
                    "symbol": f"S{s:02d}",
                    "r30": None if rng.random() < 0.05 else rng.gauss(0.0, 0.2),
                    "fwd7": None if rng.random() < 0.05 else rng.gauss(0.0, 0.1),
                }
            )
    return pl.DataFrame(rows).sort("day", "symbol")


def _historical_h24_32(
    panel: pl.DataFrame,
    col: str,
    *,
    gate: pl.Expr | None = None,
    min_coins: int = MIN_COINS,
) -> list[float]:
    """scripts/h24_32_killtests.py::ranking_spread — the loop body only."""
    p = panel.drop_nulls([col, "fwd7"])
    if gate is not None:
        p = p.filter(gate)
    spreads = []
    for _, grp in p.group_by("day", maintain_order=True):
        if grp.height < min_coins:
            continue
        g = grp.sort(col)
        bot = g.head(2)["fwd7"].mean()
        top = g.tail(2)["fwd7"].mean()
        if top is not None and bot is not None:
            spreads.append(top - bot)
    return spreads


def _historical_h15_21(panel: pl.DataFrame, col: str) -> list[float]:
    """scripts/h15_21_killtests.py H16 — nulls dropped by the CALLER, gate
    absent, min-symbols a literal 10."""
    spreads = []
    for _, grp in panel.group_by("day", maintain_order=True):
        if grp.height < 10:
            continue
        g = grp.sort(col)
        bot = g.head(2)["fwd7"].mean()
        top = g.tail(2)["fwd7"].mean()
        if top is not None and bot is not None:
            spreads.append(top - bot)
    return spreads


def test_matches_h24_32_with_nulls_dropped_inside() -> None:
    panel = _panel()
    expected = _historical_h24_32(panel, "r30")
    actual = ranking_spread_series(
        panel,
        "r30",
        outcome_column="fwd7",
        k=2,
        min_symbols=MIN_COINS,
        drop_nulls_on=("r30", "fwd7"),
    )
    assert actual == expected
    assert expected, "fixture must produce spreads or the test proves nothing"


def test_matches_h24_32_with_a_gate_and_a_lower_min_symbols() -> None:
    """H31 is the only caller that gates (r90>0) and lowers min_coins to 6."""
    panel = _panel()
    gate = pl.col("r30") > 0
    expected = _historical_h24_32(panel, "r30", gate=gate, min_coins=6)
    actual = ranking_spread_series(
        panel,
        "r30",
        outcome_column="fwd7",
        k=2,
        min_symbols=6,
        gate=gate,
        drop_nulls_on=("r30", "fwd7"),
    )
    assert actual == expected


def test_matches_h15_21_with_nulls_dropped_by_the_caller() -> None:
    panel = _panel().drop_nulls(["r30", "fwd7"])
    expected = _historical_h15_21(panel, "r30")
    actual = ranking_spread_series(
        panel,
        "r30",
        outcome_column="fwd7",
        k=2,
        min_symbols=10,
        drop_nulls_on=None,
    )
    assert actual == expected


def test_null_placement_changes_the_sample_not_only_its_size() -> None:
    """Why drop_nulls_on is a parameter rather than a default.

    Dropping inside can empty a day below the min-symbols gate, removing the
    whole day from the series — which changes the day-block bootstrap that
    consumes it, not merely the count.
    """
    panel = _panel()
    inside = ranking_spread_series(
        panel,
        "r30",
        outcome_column="fwd7",
        k=2,
        min_symbols=MIN_COINS,
        drop_nulls_on=("r30", "fwd7"),
    )
    outside = ranking_spread_series(
        panel,
        "r30",
        outcome_column="fwd7",
        k=2,
        min_symbols=MIN_COINS,
        drop_nulls_on=None,
    )
    assert inside != outside


def test_thin_days_are_skipped_entirely() -> None:
    panel = _panel(n_days=6, n_symbols=3)
    assert (
        ranking_spread_series(
            panel, "r30", outcome_column="fwd7", k=2, min_symbols=10, drop_nulls_on=None
        )
        == []
    )


def test_k_is_explicit_and_changes_the_measurement() -> None:
    panel = _panel().drop_nulls(["r30", "fwd7"])
    top2 = ranking_spread_series(
        panel, "r30", outcome_column="fwd7", k=2, min_symbols=10, drop_nulls_on=None
    )
    top4 = ranking_spread_series(
        panel, "r30", outcome_column="fwd7", k=4, min_symbols=10, drop_nulls_on=None
    )
    assert top2 != top4


# --- intraday loader -----------------------------------------------------------------


def _historical_load(data_dir: Path, symbol: str) -> pl.DataFrame:
    """scripts/h44_50_killtests.py::load (h52_55_57's copy is identical)."""
    df = pl.read_parquet(data_dir / f"{symbol}_15m.parquet").sort("ts")
    return df.with_columns(
        day=pl.col("ts").dt.date(),
        hh=pl.col("ts").dt.hour(),
        mm=pl.col("ts").dt.minute(),
    )


@pytest.fixture
def intraday_dir(tmp_path: Path) -> Path:
    start = datetime(2022, 3, 1, tzinfo=UTC)
    n = 200
    frame = pl.DataFrame(
        {
            "ts": [start + timedelta(minutes=15 * i) for i in range(n)],
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.5 + i for i in range(n)],
            "volume": [10.0 + i for i in range(n)],
        }
    )
    # Written out of order so the sort in the loader is actually exercised.
    frame.sample(fraction=1.0, shuffle=True, seed=1).write_parquet(tmp_path / "XYZUSDT_15m.parquet")
    return tmp_path


def test_load_15m_bars_matches_the_historical_loader(intraday_dir: Path) -> None:
    expected = _historical_load(intraday_dir, "XYZUSDT")
    actual = load_15m_bars(intraday_dir, "XYZUSDT")
    assert actual.equals(expected)
    assert actual.columns == expected.columns


def test_load_15m_bars_sorts_and_derives_clock_columns(intraday_dir: Path) -> None:
    frame = load_15m_bars(intraday_dir, "XYZUSDT")
    assert frame["ts"].is_sorted()
    assert frame.schema["day"] == pl.Date
    assert frame["hh"].max() is not None and 0 <= int(frame["hh"].max()) <= 23  # type: ignore[arg-type]
    assert set(frame["mm"].unique().to_list()) <= {0, 15, 30, 45}
