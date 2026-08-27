"""Stages 6 and 8: ledger search / graveyard, and replication / stress.

Search runs against the REAL migrated ledger, so a query that stops working
is caught rather than a synthetic fixture that always agrees with itself.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from martex_quant.research.ledger.query import (
    DEAD_VERDICTS,
    already_tested,
    contradictions,
    graveyard,
    kill_rate,
    search,
    strategy_grade_with_dsr,
    summarise,
    survivors,
)
from martex_quant.research.ledger.registry import load_ledger
from martex_quant.research.ledger.vocabulary import Maturity
from martex_quant.research.relationships import Cell, Condition
from martex_quant.research.robustness import (
    ReplicationRun,
    Stressor,
    StressRecord,
    StressRun,
    Variation,
    apply_stress,
    promote_after_replication,
    replicate,
    replication_record,
    stress,
    with_maturity,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ledger():  # type: ignore[no-untyped-def]
    return load_ledger(ROOT)


# --- stage 6: search and the graveyard -----------------------------------


def test_have_we_already_tested_this(ledger) -> None:  # type: ignore[no-untyped-def]
    """The question worth asking before every new idea."""
    assert already_tested(ledger, "funding")
    assert already_tested(ledger, "rotation")
    assert already_tested(ledger, "intraday")
    assert not already_tested(ledger, "options implied volatility surface")


def test_search_explains_why_each_hit_matched(ledger) -> None:  # type: ignore[no-untyped-def]
    hits = search(ledger, "funding")
    assert hits
    assert all(h.matched_on in {"hypothesis", "family", "evidence", "notes"} for h in hits)
    assert any("H08" in h.describe() for h in hits)


def test_search_is_case_insensitive(ledger) -> None:  # type: ignore[no-untyped-def]
    assert len(search(ledger, "ROTATION")) == len(search(ledger, "rotation"))


def test_the_graveyard_holds_the_dead_and_is_searchable(ledger) -> None:  # type: ignore[no-untyped-def]
    dead = graveyard(ledger)
    assert dead
    assert all(t.verdict in DEAD_VERDICTS for t in dead)
    # The intraday campaign is the corpus's largest graveyard: killed at scale.
    assert any("intraday" in t.family for t in dead)


def test_survivors_and_graveyard_do_not_overlap(ledger) -> None:  # type: ignore[no-untyped-def]
    dead_ids = {t.trial_id for t in graveyard(ledger)}
    live_ids = {t.trial_id for t in survivors(ledger)}
    assert dead_ids.isdisjoint(live_ids)


def test_kill_rate_is_reported_honestly(ledger) -> None:  # type: ignore[no-untyped-def]
    """A low kill rate is a warning sign, not an achievement."""
    rate = kill_rate(ledger)
    assert 0.0 < rate < 1.0
    assert kill_rate(ledger, "info.intraday") >= rate  # the intraday family died hardest


def test_published_dsrs_keep_the_count_they_used(ledger) -> None:  # type: ignore[no-untyped-def]
    """Search must never present these as comparable across eras."""
    found = {t.hypothesis.split("#")[0]: t.dsr_n_trials for t in strategy_grade_with_dsr(ledger)}
    assert found["H11"] == 65
    assert found["H42"] == 104
    assert found["H43"] == 107
    assert len(set(found.values())) > 1  # deliberately not one shared number


def test_contradictions_are_surfaced_not_resolved(ledger) -> None:  # type: ignore[no-untyped-def]
    pairs = contradictions(ledger)
    for a, b in pairs:
        assert a.family == b.family
        assert a.verdict != b.verdict


def test_summary_reads_as_plain_language(ledger) -> None:  # type: ignore[no-untyped-def]
    text = summarise(ledger)
    assert "trials registered : 167" in text
    assert "kill rate" in text


# --- stage 8: replication and stress -------------------------------------


def _panel(*, effect: float, seed: int, n_days: int = 400) -> pl.DataFrame:
    """A panel where the condition genuinely shifts the outcome by ``effect``."""
    rng = random.Random(seed)
    start = datetime(2021, 1, 1, tzinfo=UTC)
    rows = []
    for d in range(n_days):
        for s in range(12):
            flag = rng.random() < 0.4
            rows.append(
                {
                    "day": start + timedelta(days=d),
                    "symbol": f"S{s}",
                    "signal": 1.0 if flag else 0.0,
                    "fwd7": rng.gauss(effect if flag else 0.0, 0.03),
                }
            )
    return pl.DataFrame(rows)


CELL = Cell(Condition("signal on", pl.col("signal") > 0.5), "fwd7", 7, seed=11)


def test_a_replication_must_vary_a_declared_dimension() -> None:
    with pytest.raises(ValueError, match="not a declared replication dimension"):
        Variation("vibes", "felt right")
    assert Variation("period", "2022 only").dimension == "period"


def test_a_replication_survives_only_in_the_same_direction() -> None:
    """A significant effect the OTHER way is a refutation, not a success —
    the distinction that caught the inverted ORB result in the corpus."""
    same = replicate(
        _panel(effect=0.02, seed=5),
        "H_toy",
        "positive",
        CELL,
        Variation("period", "different window"),
        n_boot=400,
    )
    assert same.result.ci_excludes_zero and same.survived

    flipped = replicate(
        _panel(effect=-0.02, seed=6),
        "H_toy",
        "positive",
        CELL,
        Variation("period", "different window"),
        n_boot=400,
    )
    assert flipped.result.ci_excludes_zero  # an effect IS present...
    assert not flipped.survived  # ...but it refutes rather than replicates


def test_the_record_shows_failures_beside_successes() -> None:
    runs = [
        replicate(
            _panel(effect=0.02, seed=7),
            "H_toy",
            "positive",
            CELL,
            Variation("period", "2021"),
            n_boot=400,
        ),
        replicate(
            _panel(effect=0.0, seed=8),
            "H_toy",
            "positive",
            CELL,
            Variation("universe", "majors only"),
            n_boot=400,
        ),
    ]
    record = replication_record("H_toy", runs)
    assert record.attempted == 2
    assert record.survived == 1
    text = record.report()
    assert "1/2" in text and "FAILED" in text  # cherry-picking prevented by the template


def test_promotion_needs_more_than_one_varied_dimension() -> None:
    """Re-running with three different seeds is not independent replication."""
    seeds_only = replication_record(
        "H_toy",
        [
            replicate(
                _panel(effect=0.02, seed=s),
                "H_toy",
                "positive",
                CELL,
                Variation("seed", f"seed {s}"),
                n_boot=300,
            )
            for s in (11, 12, 13)
        ],
    )
    assert seeds_only.survived >= 1
    assert promote_after_replication(Maturity.L4_OUT_OF_SAMPLE, seeds_only) is (
        Maturity.L4_OUT_OF_SAMPLE
    )

    varied = replication_record(
        "H_toy",
        [
            replicate(
                _panel(effect=0.02, seed=21),
                "H_toy",
                "positive",
                CELL,
                Variation("period", "2022"),
                n_boot=300,
            ),
            replicate(
                _panel(effect=0.02, seed=22),
                "H_toy",
                "positive",
                CELL,
                Variation("universe", "majors"),
                n_boot=300,
            ),
        ],
    )
    assert promote_after_replication(Maturity.L4_OUT_OF_SAMPLE, varied) is Maturity.L5_REPLICATED


def test_surviving_a_stress_test_confers_no_significance() -> None:
    """The asymmetry that stops weak stressors being the rational choice."""
    run = stress(
        _panel(effect=0.02, seed=31),
        "H_toy",
        "positive",
        CELL,
        Stressor("costs", "10bp round trip"),
        n_boot=400,
    )
    record = StressRecord("H_toy", [run])
    assert record.survived_all
    assert apply_stress(Maturity.L6_STRESS_TESTED, record) is Maturity.L6_STRESS_TESTED
    new, why = with_maturity(record, Maturity.L6_STRESS_TESTED)
    assert new is Maturity.L6_STRESS_TESTED
    assert "confers no significance" in why


def test_breaking_under_stress_demotes_and_records_the_breaking_point() -> None:
    run = stress(
        _panel(effect=0.0, seed=41),
        "H_toy",
        "positive",
        CELL,
        Stressor("regime", "bear market only"),
        n_boot=400,
    )
    record = StressRecord("H_toy", [run])
    assert record.broke_under
    assert apply_stress(Maturity.L6_STRESS_TESTED, record) is Maturity.L3_INITIAL_EVIDENCE
    assert "breaking point: regime" in record.report()


def test_stress_never_promotes() -> None:
    """Even a finding that survives everything cannot climb via stress."""
    run = StressRun(
        parent="H_toy",
        stressor=Stressor("x", "y"),
        result=replicate(
            _panel(effect=0.03, seed=51),
            "H_toy",
            "positive",
            CELL,
            Variation("seed", "s"),
            n_boot=300,
        ).result,
        parent_direction="positive",
    )
    record = StressRecord("H_toy", [run])
    assert isinstance(run, StressRun) and not run.broke
    assert apply_stress(Maturity.L3_INITIAL_EVIDENCE, record) is Maturity.L3_INITIAL_EVIDENCE


def test_replication_run_type_is_distinct_from_stress_run() -> None:
    """The two are scored differently on purpose; conflating them would let
    stress survival count as replication evidence."""
    rep = replicate(
        _panel(effect=0.02, seed=61), "H", "positive", CELL, Variation("period", "p"), n_boot=200
    )
    assert isinstance(rep, ReplicationRun)
    assert not isinstance(rep, StressRun)
