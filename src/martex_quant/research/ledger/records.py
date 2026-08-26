"""The six record types of the research ledger.

All six are views over one append-only trial table; none can be decremented,
and deletion is impossible by construction because the source of truth is a
committed document, not a database row.

The DSR fields are the heart of Layer 2's honesty. ``dsr`` and
``dsr_n_trials`` store what was ACTUALLY published and the trial count it was
actually computed against — 65 for rotation, 104 for H42b, 6 for the two
grid-size studies. Nothing is recomputed or normalised against today's total.
See correction candidates 6-8 in docs/research/mi-layer2-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from martex_quant.research.ledger.vocabulary import (
    Grade,
    Maturity,
    Protocol,
    Verdict,
    exceeds_ceiling,
)


@dataclass(frozen=True)
class Trial:
    """One registered trial. Immutable; identity is (family, hypothesis, seq)."""

    trial_id: int  # monotonic, never reused
    hypothesis: str  # e.g. "H42b", "V2-M1"
    family: str  # hierarchical path, e.g. "strategy.momentum.rotation"
    grade: Grade
    protocol: Protocol
    verdict: Verdict
    maturity: Maturity
    source: str  # committed doc this label was derived from
    evidence: str  # verbatim text supporting the label
    ran: bool = True  # False only for registered-but-unrunnable trials
    dsr: float | None = None  # AS PUBLISHED — never recomputed
    dsr_n_trials: int | None = None  # the count it was actually deflated against
    selection_set: str | None = None  # which comparison it competed in
    notes: str = ""

    def __post_init__(self) -> None:
        if exceeds_ceiling(self.protocol, self.maturity):
            raise ValueError(
                f"{self.hypothesis}: maturity {self.maturity} exceeds the ceiling for "
                f"protocol {self.protocol}"
            )
        if (self.dsr is None) != (self.dsr_n_trials is None):
            raise ValueError(
                f"{self.hypothesis}: dsr and dsr_n_trials must be recorded together — "
                "a DSR without the trial count it used is exactly the ambiguity "
                "correction candidate 6 is about"
            )


@dataclass(frozen=True)
class Family:
    """A declared region of hypothesis space and its error budget.

    ``declared_cells`` is what the family DECLARED, not what it ran. A grid of
    20 features x 10 horizons costs 200 even if 50 cells were executed; that
    closes the "declare big, run small" loophole.
    """

    family_id: str  # hierarchical path
    description: str
    declared_cells: int
    period: str  # the research period this declaration belongs to
    source: str

    def __post_init__(self) -> None:
        if self.declared_cells < 1:
            raise ValueError(f"{self.family_id}: declared_cells must be positive")


@dataclass(frozen=True)
class Replication:
    """A re-test of an existing claim. Spends no error budget (§4.3)."""

    parent_hypothesis: str
    varied: str  # what was deliberately changed
    survived: bool
    source: str
    evidence: str


@dataclass(frozen=True)
class StressTest:
    """Can only demote. Surviving confers no significance (§4.4)."""

    parent_hypothesis: str
    stressor: str
    broke: bool
    source: str
    evidence: str


@dataclass(frozen=True)
class EvidenceDescriptor:
    """Amendment 9: research volume is not independent evidence.

    Reported instead of a bare trial count. The weakest dimension is the
    honest summary — 5,000 trials over one period with no replication is one
    observation examined exhaustively.
    """

    research_volume: int
    independent_families: int
    independent_periods: int
    replications_attempted: int
    replications_survived: int

    @property
    def weakest(self) -> str:
        if self.replications_survived == 0:
            return "no surviving replication"
        if self.independent_periods <= 1:
            return "single period"
        if self.independent_families <= 1:
            return "single family"
        return "none — all dimensions above one"


@dataclass
class Ledger:
    """The append-only corpus. Views over it are the six records."""

    trials: list[Trial] = field(default_factory=list)
    families: list[Family] = field(default_factory=list)
    replications: list[Replication] = field(default_factory=list)
    stress_tests: list[StressTest] = field(default_factory=list)

    # --- the six records -------------------------------------------------

    @property
    def global_history(self) -> list[Trial]:
        """Record 1. Audit, NOT an inference parameter."""
        return list(self.trials)

    def family_trials(self, family_id: str) -> list[Trial]:
        """Record 2. Includes descendants: a path prefix owns its subtree."""
        prefix = family_id + "."
        return [t for t in self.trials if t.family == family_id or t.family.startswith(prefix)]

    @property
    def exploratory(self) -> list[Trial]:
        """Record 3."""
        return [t for t in self.trials if t.protocol is Protocol.EXPLORATORY]

    @property
    def confirmatory(self) -> list[Trial]:
        """Record 4."""
        return [t for t in self.trials if t.protocol is Protocol.CONFIRMATORY]

    @property
    def replication_trials(self) -> list[Trial]:
        """Record 5."""
        return [t for t in self.trials if t.protocol is Protocol.REPLICATION]

    @property
    def strategy_relevant(self) -> list[Trial]:
        """Record 6. AMBIGUOUS trials count here too — conservatively."""
        return [t for t in self.trials if t.grade in (Grade.STRATEGY, Grade.AMBIGUOUS)]

    # --- counts ----------------------------------------------------------

    @property
    def n_registered(self) -> int:
        return len(self.trials)

    @property
    def n_run(self) -> int:
        return sum(1 for t in self.trials if t.ran)

    @property
    def m_lifetime(self) -> int:
        """Permanent cumulative declared cells; never reset (amendment 2)."""
        return sum(f.declared_cells for f in self.families)

    def m_annual(self, period: str) -> int:
        """Active budget denominator for one research period."""
        return sum(f.declared_cells for f in self.families if f.period == period)
