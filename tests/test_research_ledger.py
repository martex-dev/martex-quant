"""The 12 Layer 2 invariants, as executable tests, plus migration checks.

Goldens cannot protect this layer — it changes nothing the research scripts
print, so a mislabelled family, protocol or grade would fail no fixture.
These tests are the safety net instead.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from martex_quant.research.ledger.records import EvidenceDescriptor, Family, Trial
from martex_quant.research.ledger.registry import (
    index_fingerprint,
    ledger_claims,
    load_ledger,
    rebuild_index,
    with_trial,
)
from martex_quant.research.ledger.vocabulary import (
    HISTORICAL_VERDICT_ALIASES,
    Grade,
    Maturity,
    Protocol,
    Verdict,
    exceeds_ceiling,
)
from martex_quant.stats.multiple_testing import (
    DEFAULT_Q_GLOBAL,
    allocate_family_budget,
    by_correction_factor,
    first_discovery_threshold,
    step_up,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ledger():  # type: ignore[no-untyped-def]
    return load_ledger(ROOT)


# --- invariants 1-5: the append-only trial table --------------------------


def test_invariant_1_trial_ids_are_monotonic_and_unique(ledger) -> None:  # type: ignore[no-untyped-def]
    ids = [t.trial_id for t in ledger.trials]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_invariant_2_global_history_is_non_decreasing(ledger) -> None:  # type: ignore[no-untyped-def]
    before = ledger.n_registered
    grown = with_trial(
        ledger,
        Trial(
            trial_id=max(t.trial_id for t in ledger.trials) + 1,
            hypothesis="H999",
            family="info.test",
            grade=Grade.INFO,
            protocol=Protocol.EXPLORATORY,
            verdict=Verdict.NOISE,
            maturity=Maturity.L1_EXPLORATORY,
            source="test",
            evidence="test",
        ),
    )
    assert grown.n_registered == before + 1
    assert ledger.n_registered == before  # the original is untouched


def test_invariant_2b_trial_ids_are_never_reused(ledger) -> None:  # type: ignore[no-untyped-def]
    existing = ledger.trials[0]
    with pytest.raises(ValueError, match="never reused"):
        with_trial(ledger, existing)


def test_invariant_3_every_trial_has_exactly_one_family_and_protocol(ledger) -> None:  # type: ignore[no-untyped-def]
    for t in ledger.trials:
        assert isinstance(t.family, str) and t.family
        assert isinstance(t.protocol, Protocol)
        assert isinstance(t.grade, Grade)


def test_invariant_4_family_cells_are_declared_positive(ledger) -> None:  # type: ignore[no-untyped-def]
    for f in ledger.families:
        assert f.declared_cells >= 1
    with pytest.raises(ValueError, match="declared_cells must be positive"):
        Family(family_id="x", description="", declared_cells=0, period="2026", source="t")


def test_invariant_5_cells_run_never_exceed_cells_declared(ledger) -> None:  # type: ignore[no-untyped-def]
    for f in ledger.families:
        assert len(ledger.family_trials(f.family_id)) <= f.declared_cells
    with pytest.raises(ValueError, match="declared only"):
        step_up([0.01, 0.02, 0.03], declared_cells=2, q=0.1, procedure="by")


# --- invariant 6: the alpha budget ---------------------------------------


def test_invariant_6_family_budgets_sum_within_the_global_budget() -> None:
    sizes = [20, 100, 1000, 8000]
    m_annual = sum(sizes)
    total = sum(allocate_family_budget(s, m_annual, DEFAULT_Q_GLOBAL) for s in sizes)
    assert total <= DEFAULT_Q_GLOBAL + 1e-12


def test_proportional_allocation_gives_every_family_the_same_first_bar() -> None:
    """The property that makes volume charged rather than hidden: a large
    family buys NO discount on its first discovery."""
    sizes = [20, 100, 1000, 8000]
    m_annual = sum(sizes)
    thresholds = {s: allocate_family_budget(s, m_annual, DEFAULT_Q_GLOBAL) / s for s in sizes}
    expected = first_discovery_threshold(m_annual, DEFAULT_Q_GLOBAL)
    for s, got in thresholds.items():
        assert got == pytest.approx(expected), f"family of {s} cells got a different first bar"


def test_by_is_stricter_than_bh_and_matches_the_documented_factors() -> None:
    assert by_correction_factor(10) == pytest.approx(2.928968, abs=1e-5)
    assert by_correction_factor(1000) == pytest.approx(7.485471, abs=1e-5)
    p = [0.001, 0.02, 0.5]
    by = step_up(p, declared_cells=100, q=0.1, procedure="by")
    bh = step_up(p, declared_cells=100, q=0.1, procedure="bh")
    assert sum(d.rejected for d in by) <= sum(d.rejected for d in bh)


def test_declared_not_run_is_the_fdr_denominator() -> None:
    """Declaring 200 and running 3 costs 200 — the loophole this closes."""
    p = [0.0004, 0.02, 0.5]
    few = step_up(p, declared_cells=3, q=0.1, procedure="by")
    many = step_up(p, declared_cells=200, q=0.1, procedure="by")
    assert sum(d.rejected for d in few) > sum(d.rejected for d in many)


# --- invariants 7-8: the wall --------------------------------------------


def test_invariant_7_exploratory_cannot_claim_more_than_L1() -> None:
    assert exceeds_ceiling(Protocol.EXPLORATORY, Maturity.L3_INITIAL_EVIDENCE)
    assert not exceeds_ceiling(Protocol.EXPLORATORY, Maturity.L1_EXPLORATORY)
    with pytest.raises(ValueError, match="exceeds the ceiling"):
        Trial(
            trial_id=1,
            hypothesis="H_bad",
            family="info.test",
            grade=Grade.INFO,
            protocol=Protocol.EXPLORATORY,
            verdict=Verdict.SIGNAL,
            maturity=Maturity.L4_OUT_OF_SAMPLE,
            source="t",
            evidence="t",
        )


def test_invariant_8_maturity_never_exceeds_its_protocol_ceiling(ledger) -> None:  # type: ignore[no-untyped-def]
    for t in ledger.trials:
        assert not exceeds_ceiling(t.protocol, t.maturity)


# --- invariants 9-10: storage --------------------------------------------


def test_invariant_9_a_dsr_cannot_be_recorded_without_its_trial_count() -> None:
    """Correction candidate 6 made structurally impossible for new records."""
    with pytest.raises(ValueError, match="must be recorded together"):
        Trial(
            trial_id=1,
            hypothesis="H_bad",
            family="strategy.test",
            grade=Grade.STRATEGY,
            protocol=Protocol.CONFIRMATORY,
            verdict=Verdict.CANDIDATE,
            maturity=Maturity.L4_OUT_OF_SAMPLE,
            source="t",
            evidence="t",
            dsr=0.99,
        )


def test_invariant_10_index_rebuild_is_deterministic(ledger) -> None:  # type: ignore[no-untyped-def]
    first = index_fingerprint(rebuild_index(ledger))
    second = index_fingerprint(rebuild_index(load_ledger(ROOT)))
    assert first == second


def test_index_is_disposable_and_derived(ledger, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "index.sqlite"
    rebuild_index(ledger, path).close()
    assert path.exists()
    path.unlink()
    rebuilt = rebuild_index(load_ledger(ROOT), path)
    assert rebuilt.execute("SELECT COUNT(*) FROM trial").fetchone()[0] == ledger.n_registered


# --- invariants 11-12: reporting -----------------------------------------


def test_invariant_11_every_recorded_dsr_carries_the_count_it_used(ledger) -> None:
    """Historical DSRs are preserved exactly, each with its own n_trials —
    65 for rotation, 104 for H42b, 107 for H43a. None normalised to 125."""
    published = {
        t.hypothesis.split("#")[0]: (t.dsr, t.dsr_n_trials)
        for t in ledger.trials
        if t.dsr is not None
    }
    assert published["H11"] == (0.990, 65)
    assert published["H12"] == (0.777, 57)
    assert published["H41"] == (0.995, 104)
    assert published["H42"] == (0.992, 104)
    assert published["H43"] == (1.000, 107)
    assert all(n is not None for _, n in published.values())
    assert {n for _, n in published.values()} != {125}, "nothing may be normalised to today's total"


def test_invariant_12_evidence_descriptor_reports_its_weakest_dimension() -> None:
    """Amendment 9: volume is a burden disclosure, not a strength claim."""
    exhaustive_but_thin = EvidenceDescriptor(
        research_volume=5000,
        independent_families=1,
        independent_periods=1,
        replications_attempted=0,
        replications_survived=0,
    )
    assert exhaustive_but_thin.weakest == "no surviving replication"
    assert EvidenceDescriptor(10, 1, 1, 3, 2).weakest == "single period"
    assert EvidenceDescriptor(10, 3, 4, 3, 2).weakest.startswith("none")


# --- migration reconciliation --------------------------------------------


def test_migration_reconciles_to_the_ledgers_own_claimed_totals(ledger) -> None:  # type: ignore[no-untyped-def]
    claims = ledger_claims(ROOT)
    assert ledger.n_registered == claims["registered"] == 172
    assert ledger.n_run == claims["run"] == 171
    assert ledger.n_registered - ledger.n_run == claims["data_blocked"] == 1


def test_the_documentation_gap_is_carried_explicitly_not_absorbed(ledger) -> None:  # type: ignore[no-untyped-def]
    """The honest finding: documented deltas do not sum to the claimed total.

    The gap is checked against the ledger's OWN claim rather than a literal, so
    it stays a real reconciliation as the ledger grows: H58 added 5 documented
    trials and 5 to the total, leaving the gap at 5 where it was."""
    claims = ledger_claims(ROOT)
    gap = claims["registered"] - claims["documented"]
    unallocated = [t for t in ledger.trials if t.family == "unallocated"]
    assert len(unallocated) == gap
    assert all(t.grade is Grade.AMBIGUOUS for t in unallocated)


def test_every_migrated_trial_cites_a_committed_source(ledger) -> None:  # type: ignore[no-untyped-def]
    for t in ledger.trials:
        assert t.source, f"{t.hypothesis} has no source"
        assert t.evidence, f"{t.hypothesis} has no evidence"
        if t.family != "unallocated":
            assert (ROOT / t.source).exists(), f"{t.hypothesis} cites a missing file: {t.source}"


def test_the_six_records_partition_the_corpus(ledger) -> None:  # type: ignore[no-untyped-def]
    assert len(ledger.global_history) == ledger.n_registered
    by_protocol = (
        len(ledger.exploratory) + len(ledger.confirmatory) + len(ledger.replication_trials)
    )
    assert by_protocol <= ledger.n_registered
    assert len(ledger.strategy_relevant) >= 1
    assert (
        sum(len(ledger.family_trials(f.family_id)) for f in ledger.families) == ledger.n_registered
    )


def test_m_lifetime_is_permanent_and_m_annual_is_the_active_denominator(ledger) -> None:  # type: ignore[no-untyped-def]
    assert ledger.m_lifetime == ledger.n_registered
    assert ledger.m_annual("2026") == ledger.m_lifetime
    assert ledger.m_annual("2027") == 0  # a new period resets the ACTIVE budget only
    assert ledger.m_lifetime > 0  # ...and never the lifetime total


def test_historical_verdict_aliases_cover_the_corpus_vocabulary() -> None:
    for word in (
        "killed",
        "noise",
        "signal",
        "rejected",
        "eligible",
        "candidate",
        "validated",
        "confirmed",
        "survived",
        "inconclusive",
        "data-blocked",
    ):
        assert word in HISTORICAL_VERDICT_ALIASES
    assert not math.isnan(DEFAULT_Q_GLOBAL)
