"""Relationship engine: reproduction of a published result, plus guards.

The first test is the important one. If the engine cannot reproduce H40's
published figures exactly, it is not measuring what the ledger measured, and
every future finding it produces is incomparable with the existing corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.features.panel import (
    daily_panel,
    forward_return,
    momentum,
    rolling_max_close,
    rolling_mean_of,
    true_range,
)
from martex_quant.research.ledger.records import Family
from martex_quant.research.relationships import (
    Cell,
    Condition,
    horizon_profile,
    measure_cell,
    run_family,
)

ROOT = Path(__file__).resolve().parents[1]


def _has_lake() -> bool:
    return (ROOT / "data" / "lake" / "catalog.json").exists()


requires_lake = pytest.mark.skipif(not _has_lake(), reason="no local data lake (CI)")


@pytest.fixture(scope="module")
def h40_panel() -> pl.DataFrame:
    """The exact panel h33_40 builds for H40."""
    store = ParquetStore(ROOT / "data" / "lake")
    universe = json.loads((ROOT / "config" / "universe.json").read_text(encoding="utf-8"))[
        "symbols"
    ]
    return daily_panel(
        store,
        universe,
        base_columns=("close", "high", "low", "ret"),
        feature_stages=[
            [
                momentum(30),
                momentum(90),
                momentum(180),
                rolling_max_close(30, name="hi30"),
                true_range(),
                forward_return(7),
                forward_return(30),
            ],
            [rolling_mean_of("tr", 14, name="atr14")],
        ],
        on_missing_symbol="skip",
    )


@requires_lake
@pytest.mark.slow
def test_reproduces_the_published_h40_trailing_stop_result(h40_panel: pl.DataFrame) -> None:
    """H40, as published: 'stop-fired vs not | uptrend, fwd30'
    n=10247  diff -8.77%  CI [-15.57%, -2.17%]  SIGNAL.

    Same panel, same condition, same seed (4010) and block (30) as
    h33_40_killtests. Anything else and the engine is not comparable with the
    corpus it has to extend.
    """
    panel = h40_panel.drop_nulls(["r90", "atr14", "hi30", "fwd30"]).filter(pl.col("r90") > 0)
    fired = Condition(
        name="stop fired (2xATR14 below the 30d high)",
        expr=(pl.col("hi30") - pl.col("close")) >= 2.0 * pl.col("atr14"),
    )
    result = measure_cell(panel, Cell(condition=fired, outcome="fwd30", horizon=30, seed=4010))

    assert result.n_a == 10_247
    assert result.effect == pytest.approx(-0.0877, abs=5e-5)
    assert result.ci_low == pytest.approx(-0.1557, abs=5e-5)
    assert result.ci_high == pytest.approx(-0.0217, abs=5e-5)
    assert result.ci_excludes_zero
    assert result.direction == "negative"


@requires_lake
@pytest.mark.slow
def test_the_p_value_agrees_with_the_published_interval(h40_panel: pl.DataFrame) -> None:
    """New machinery, checked against the old decision: a CI that excludes
    zero at 95% must carry p < 0.05, and one that includes it must not."""
    panel = h40_panel.drop_nulls(["r90", "atr14", "hi30", "fwd30"]).filter(pl.col("r90") > 0)
    fired = Condition("fired", (pl.col("hi30") - pl.col("close")) >= 2.0 * pl.col("atr14"))
    hit = measure_cell(panel, Cell(fired, "fwd30", 30, seed=4010))
    assert hit.ci_excludes_zero and hit.p_value < 0.05

    noise = Condition("coin flip", pl.col("close").hash(seed=7) % 2 == 0)
    miss = measure_cell(panel, Cell(noise, "fwd30", 30, seed=99))
    assert not miss.ci_excludes_zero
    assert miss.p_value > 0.05


@requires_lake
@pytest.mark.slow
def test_horizon_profile_shows_where_an_effect_lives(h40_panel: pl.DataFrame) -> None:
    """A real effect should not appear at exactly one horizon and nowhere
    else. H40's stop signal is a 30-day effect; the profile makes that
    visible rather than leaving it to a single lucky cell."""
    panel = h40_panel.drop_nulls(["r90", "atr14", "hi30", "fwd7", "fwd30"]).filter(
        pl.col("r90") > 0
    )
    fired = Condition("fired", (pl.col("hi30") - pl.col("close")) >= 2.0 * pl.col("atr14"))
    profile = horizon_profile(panel, fired, [(7, "fwd7"), (30, "fwd30")], base_seed=4000)

    assert [r.cell.horizon for r in profile] == [7, 30]
    assert all(r.effect < 0 for r in profile)  # stops help at both horizons
    assert abs(profile[1].effect) > abs(profile[0].effect)  # and more at 30d


# --- dredging guards (no lake needed) ------------------------------------


def _toy_panel(n_days: int = 400, seed: int = 3) -> pl.DataFrame:
    import random

    rng = random.Random(seed)
    from datetime import UTC, datetime, timedelta

    start = datetime(2021, 1, 1, tzinfo=UTC)
    rows = []
    for d in range(n_days):
        for s in range(12):
            rows.append(
                {
                    "day": start + timedelta(days=d),
                    "symbol": f"S{s}",
                    "signal": rng.gauss(0, 1),
                    "fwd7": rng.gauss(0, 0.05),
                }
            )
    return pl.DataFrame(rows)


def test_running_more_cells_than_declared_is_refused() -> None:
    """The declaration is binding: 'declare small, keep testing' must not be
    the path of least resistance."""
    panel = _toy_panel()
    family = Family("info.test", "toy", declared_cells=2, period="2026", source="t")
    cells = [
        Cell(Condition(f"c{i}", pl.col("signal") > i / 10), "fwd7", 7, seed=100 + i)
        for i in range(3)
    ]
    with pytest.raises(ValueError, match="declared 2 cells but 3"):
        run_family(panel, family, cells, m_annual=1000, n_boot=200)


def test_declared_but_unrun_cells_still_cost_budget() -> None:
    """Declaring 50 and running 2 is corrected for 50. Otherwise a family
    could buy a cheap bar by declaring narrowly and testing broadly later."""
    panel = _toy_panel()
    cells = [
        Cell(Condition(f"c{i}", pl.col("signal") > i / 10), "fwd7", 7, seed=200 + i)
        for i in range(2)
    ]
    narrow = run_family(
        panel,
        Family("info.a", "", declared_cells=2, period="2026", source="t"),
        cells,
        m_annual=1000,
        n_boot=200,
    )
    broad = run_family(
        panel,
        Family("info.b", "", declared_cells=50, period="2026", source="t"),
        cells,
        m_annual=1000,
        n_boot=200,
    )
    assert broad.q_allocated > narrow.q_allocated  # a bigger family gets more budget...
    # ...but spread over more declared cells, so each cell's bar is no easier.
    assert broad.q_allocated / 50 == pytest.approx(narrow.q_allocated / 2)


def test_pure_noise_yields_no_discoveries() -> None:
    """The engine's most important negative property."""
    panel = _toy_panel()
    family = Family("info.noise", "", declared_cells=6, period="2026", source="t")
    cells = [
        Cell(Condition(f"c{i}", pl.col("signal") > i / 5 - 0.5), "fwd7", 7, seed=300 + i)
        for i in range(6)
    ]
    outcome = run_family(panel, family, cells, m_annual=1000, n_boot=400)
    assert outcome.discoveries == []
    assert "0 survive FDR" in outcome.summary()
