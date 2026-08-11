"""Stage 8: replication and stress testing.

Two procedures with deliberately ASYMMETRIC accounting, because they answer
different questions and the incentives have to match:

**Replication** re-tests an existing claim under a declared variation — a
different period, universe, or parameterisation. It spends no error budget:
correcting a replication for multiplicity would make replication *harder* the
more you replicate, which inverts the incentive you want. It is scored as
``survived / attempted``, and failures are attached to the parent forever.

**Stress** tries to break a finding. Surviving a stress test confers NO
additional significance — only demotion is possible. That asymmetry is the
point: if survival were rewarded, the rational move would be to design weak
stresses, and the whole exercise would become theatre.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

from trading_bot.research.ledger.vocabulary import Maturity, maturity_rank
from trading_bot.research.relationships import Cell, CellResult, measure_cell

# Dimensions a replication is allowed to vary. Declared in advance so
# "we varied something" cannot be decided after seeing the result.
VARIATION_DIMENSIONS = ("period", "universe", "parameterisation", "venue", "seed")


@dataclass(frozen=True)
class Variation:
    """One declared change from the parent test's conditions."""

    dimension: str
    description: str

    def __post_init__(self) -> None:
        if self.dimension not in VARIATION_DIMENSIONS:
            raise ValueError(
                f"'{self.dimension}' is not a declared replication dimension; "
                f"choose from {VARIATION_DIMENSIONS}"
            )


@dataclass(frozen=True)
class ReplicationRun:
    parent: str  # parent hypothesis id
    variation: Variation
    result: CellResult
    parent_direction: str

    @property
    def survived(self) -> bool:
        """A replication survives only if the effect is present AND points the
        same way. A significant effect in the opposite direction is a
        refutation, not a success — that distinction is what caught the
        inverted ORB result in the existing corpus."""
        return self.result.ci_excludes_zero and self.result.direction == self.parent_direction


@dataclass(frozen=True)
class ReplicationRecord:
    """The permanent record attached to a finding. Failures included."""

    parent: str
    runs: list[ReplicationRun]

    @property
    def attempted(self) -> int:
        return len(self.runs)

    @property
    def survived(self) -> int:
        return sum(1 for r in self.runs if r.survived)

    @property
    def dimensions_varied(self) -> set[str]:
        return {r.variation.dimension for r in self.runs}

    def report(self) -> str:
        """Rendered so failures sit next to successes — the template, not
        discipline, is what prevents cherry-picking."""
        lines = [f"{self.parent}: replication {self.survived}/{self.attempted}"]
        for run in self.runs:
            mark = "survived" if run.survived else "FAILED"
            lines.append(
                f"  [{mark}] {run.variation.dimension}: {run.variation.description} — "
                f"effect {run.result.effect:+.2%} "
                f"CI [{run.result.ci_low:+.2%}, {run.result.ci_high:+.2%}]"
            )
        return "\n".join(lines)


def replicate(
    panel: pl.DataFrame,
    parent: str,
    parent_direction: str,
    cell: Cell,
    variation: Variation,
    *,
    n_boot: int = 5_000,
) -> ReplicationRun:
    """Re-test a claim on a varied panel or cell. Spends no error budget."""
    return ReplicationRun(
        parent=parent,
        variation=variation,
        result=measure_cell(panel, cell, n_boot=n_boot),
        parent_direction=parent_direction,
    )


def replication_record(parent: str, runs: Sequence[ReplicationRun]) -> ReplicationRecord:
    return ReplicationRecord(parent=parent, runs=list(runs))


# --- stress ---------------------------------------------------------------


@dataclass(frozen=True)
class Stressor:
    """A deliberate attempt to break a finding."""

    name: str
    description: str


@dataclass(frozen=True)
class StressRun:
    parent: str
    stressor: Stressor
    result: CellResult
    parent_direction: str

    @property
    def broke(self) -> bool:
        """The finding broke if the effect no longer holds, or flipped."""
        return not (self.result.ci_excludes_zero and self.result.direction == self.parent_direction)


@dataclass(frozen=True)
class StressRecord:
    parent: str
    runs: list[StressRun]

    @property
    def broke_under(self) -> list[StressRun]:
        return [r for r in self.runs if r.broke]

    @property
    def survived_all(self) -> bool:
        return not self.broke_under

    def report(self) -> str:
        if self.survived_all:
            return (
                f"{self.parent}: survived {len(self.runs)} stressor(s) — "
                "no significance gained (survival confers none)"
            )
        lines = [f"{self.parent}: BROKE under {len(self.broke_under)}/{len(self.runs)} stressor(s)"]
        for run in self.broke_under:
            lines.append(
                f"  breaking point: {run.stressor.name} — {run.stressor.description} "
                f"(effect {run.result.effect:+.2%}, "
                f"CI [{run.result.ci_low:+.2%}, {run.result.ci_high:+.2%}])"
            )
        return "\n".join(lines)


def stress(
    panel: pl.DataFrame,
    parent: str,
    parent_direction: str,
    cell: Cell,
    stressor: Stressor,
    *,
    n_boot: int = 5_000,
) -> StressRun:
    return StressRun(
        parent=parent,
        stressor=stressor,
        result=measure_cell(panel, cell, n_boot=n_boot),
        parent_direction=parent_direction,
    )


def apply_stress(current: Maturity, record: StressRecord) -> Maturity:
    """Stress can only DEMOTE. Surviving returns the maturity unchanged.

    Demotion is to L3 (initial evidence): a finding that breaks under stress
    is not worthless — its original measurement stands — but it can no longer
    claim to have been stress-tested, and it certainly cannot sit at L6.
    """
    if record.survived_all:
        return current
    demoted = Maturity.L3_INITIAL_EVIDENCE
    return demoted if maturity_rank(demoted) < maturity_rank(current) else current


def promote_after_replication(
    current: Maturity, record: ReplicationRecord, *, min_survived: int = 1
) -> Maturity:
    """Replication is the only route to L5, and only on independent survival.

    Requires at least ``min_survived`` surviving replications AND that they
    varied more than one dimension — a claim re-tested three times by only
    changing the seed has not been independently replicated.
    """
    if record.survived < min_survived or len(record.dimensions_varied) < 2:
        return current
    target = Maturity.L5_REPLICATED
    return target if maturity_rank(target) > maturity_rank(current) else current


def with_maturity(record: StressRecord, current: Maturity) -> tuple[Maturity, str]:
    """Convenience: the new maturity and a one-line explanation."""
    new = apply_stress(current, record)
    if new == current:
        return new, "unchanged — surviving a stress test confers no significance"
    return new, f"demoted {current.value} -> {new.value} by {len(record.broke_under)} stressor(s)"
