"""Relationship research engine: does a market condition predict an outcome?

Layer 5. This is the first layer that can GENERATE trials, so it is built to
make dredging awkward rather than convenient:

* A test cannot run outside a declared family. The family fixes its cell
  count in advance, and running more cells than declared raises.
* Every cell's p-value goes through the family's allocated share of the
  global error budget (``stats.multiple_testing``), Benjamini-Yekutieli by
  default. A raw per-cell CI is reported too, because that is what the
  historical corpus used — but the FDR verdict is the one that counts.
* Exploratory work is capped at maturity L1 by the ledger vocabulary; nothing
  here can promote a finding on its own.

The measurement itself is deliberately the SAME one the corpus already used:
split a panel by a condition, compare mean forward outcomes, and get a
confidence interval from the day-block bootstrap. A test here reproduces
H40's published result exactly, which is the evidence that the engine
measures what the ledger measured.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

from trading_bot.research.ledger.records import Family
from trading_bot.stats.bootstrap import two_group_diff_ci, two_group_diff_pvalue
from trading_bot.stats.multiple_testing import (
    DEFAULT_Q_GLOBAL,
    Procedure,
    allocate_family_budget,
    step_up,
)

BLOCK_DAYS = 30
N_BOOT = 5_000


@dataclass(frozen=True)
class Condition:
    """A boolean split of the panel: rows where ``expr`` holds are group A."""

    name: str
    expr: pl.Expr


@dataclass(frozen=True)
class Cell:
    """One declared test: condition -> outcome, at one horizon."""

    condition: Condition
    outcome: str  # column holding the forward outcome, e.g. "fwd30"
    horizon: int  # bars ahead the outcome looks; for the profile axis
    seed: int


@dataclass(frozen=True)
class CellResult:
    cell: Cell
    n_a: int
    effect: float  # mean(outcome | condition) - mean(outcome | not condition)
    ci_low: float
    ci_high: float
    p_value: float
    ci_excludes_zero: bool  # the historical per-test decision, for continuity
    survives_fdr: bool | None = None  # filled in by run_family

    @property
    def direction(self) -> str:
        return "positive" if self.effect > 0 else "negative"


@dataclass(frozen=True)
class FamilyOutcome:
    family: Family
    q_allocated: float
    results: list[CellResult]

    @property
    def discoveries(self) -> list[CellResult]:
        return [r for r in self.results if r.survives_fdr]

    def summary(self) -> str:
        raw = sum(r.ci_excludes_zero for r in self.results)
        kept = len(self.discoveries)
        return (
            f"{self.family.family_id}: {len(self.results)} cells run of "
            f"{self.family.declared_cells} declared, q_k={self.q_allocated:.5f} — "
            f"{raw} raw CI hits, {kept} survive FDR"
        )


def _by_day(panel: pl.DataFrame, condition: Condition, outcome: str) -> pl.DataFrame:
    """Per-day sums and counts for each side of the split.

    Blocks are contiguous DATE ranges with the cross-section intact, matching
    every historical kill test: symbols are correlated, so resampling
    symbol-days independently would fake precision.
    """
    tagged = panel.with_columns(
        a=pl.when(condition.expr).then(pl.col(outcome)),
        b=pl.when(~condition.expr).then(pl.col(outcome)),
    )
    return (
        tagged.group_by("day")
        .agg(
            a_sum=pl.col("a").sum(),
            a_n=pl.col("a").is_not_null().sum(),
            b_sum=pl.col("b").sum(),
            b_n=pl.col("b").is_not_null().sum(),
        )
        .sort("day")
        .fill_null(0.0)
    )


def measure_cell(
    panel: pl.DataFrame, cell: Cell, *, block: int = BLOCK_DAYS, n_boot: int = N_BOOT
) -> CellResult:
    """One condition-versus-rest comparison with a day-block bootstrap CI."""
    frame = panel.drop_nulls([cell.outcome])
    by_day = _by_day(frame, cell.condition, cell.outcome)
    columns = [by_day[c].to_list() for c in ("a_sum", "a_n", "b_sum", "b_n")]
    kwargs = {
        "block": block,
        "seed": cell.seed,
        "n_boot": n_boot,
        "empty_denominator": "guard",
        "short_series": "error",
    }
    ci = two_group_diff_ci(*columns, **kwargs)  # type: ignore[arg-type]
    _, p_value = two_group_diff_pvalue(*columns, **kwargs)  # type: ignore[arg-type]
    return CellResult(
        cell=cell,
        n_a=ci.n,
        effect=ci.point,
        ci_low=ci.low,
        ci_high=ci.high,
        p_value=p_value,
        ci_excludes_zero=ci.low > 0.0 or ci.high < 0.0,
    )


def horizon_profile(
    panel: pl.DataFrame,
    condition: Condition,
    outcomes: Sequence[tuple[int, str]],
    *,
    base_seed: int,
    block: int = BLOCK_DAYS,
    n_boot: int = N_BOOT,
) -> list[CellResult]:
    """The same condition measured across several horizons.

    The profile is the point: an effect that appears only at one horizon and
    vanishes either side of it is far weaker evidence than one that decays
    smoothly, even when both clear the same bar at their best horizon. Each
    horizon gets its own deterministic seed so the profile is reproducible.
    """
    return [
        measure_cell(
            panel,
            Cell(condition=condition, outcome=column, horizon=horizon, seed=base_seed + horizon),
            block=block,
            n_boot=n_boot,
        )
        for horizon, column in outcomes
    ]


def run_family(
    panel: pl.DataFrame,
    family: Family,
    cells: Sequence[Cell],
    *,
    m_annual: int,
    q_global: float = DEFAULT_Q_GLOBAL,
    procedure: Procedure = "by",
    block: int = BLOCK_DAYS,
    n_boot: int = N_BOOT,
) -> FamilyOutcome:
    """Run a declared family and apply its share of the global error budget.

    Raises if more cells are run than the family declared — the declaration
    is binding, which is what stops "declare small, keep testing" from being
    the path of least resistance.
    """
    if len(cells) > family.declared_cells:
        raise ValueError(
            f"{family.family_id} declared {family.declared_cells} cells but {len(cells)} were "
            "supplied; amend the family declaration before running more"
        )
    q_k = allocate_family_budget(family.declared_cells, m_annual, q_global)
    results = [measure_cell(panel, cell, block=block, n_boot=n_boot) for cell in cells]
    decisions = step_up(
        [r.p_value for r in results],
        declared_cells=family.declared_cells,
        q=q_k,
        procedure=procedure,
    )
    survived = {d.index: d.rejected for d in decisions}
    return FamilyOutcome(
        family=family,
        q_allocated=q_k,
        results=[
            CellResult(**{**vars(r), "survives_fdr": survived[i]}) for i, r in enumerate(results)
        ],
    )
