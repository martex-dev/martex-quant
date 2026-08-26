"""Multiple-testing control for the research ledger.

Implements the approved accounting design: hierarchical FDR with a
proportionally allocated global budget, so exploration is uncapped but
priced.

Nothing here touches a historical result. The corpus contains no multiplicity
correction at all — all 10 historical significance decisions are raw
per-test 95% CIs — and applying one retroactively would change published
verdicts. This machinery is for NEW trials.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

# q_global is a methodological PARAMETER, not a truth (amendment 3). It is
# versioned with every result computed under it and may never be re-tuned
# against results.
DEFAULT_Q_GLOBAL = 0.10

Procedure = Literal["by", "bh"]


def by_correction_factor(m: int) -> float:
    """Benjamini-Yekutieli's c(m) = sum(1/i), valid under ARBITRARY dependence.

    The default (amendment 4). Research families here overlap heavily —
    shared bars, nested horizons, correlated features — so independence
    cannot be assumed. The cost is real: c(1000) = 7.49, so thresholds are
    7.5x stricter than BH at that size.
    """
    if m < 1:
        raise ValueError("m must be positive")
    return sum(1.0 / i for i in range(1, m + 1))


def allocate_family_budget(declared_cells: int, m_annual: int, q_global: float) -> float:
    """q_k = q_global * m_k / M_annual.

    A conservative split of the global FDR budget. Its key property, and the
    reason it satisfies the "families must not hide exploratory volume"
    constraint: the threshold the MOST significant cell in any family must
    clear is q_k / m_k = q_global / M_annual — identical for every family
    regardless of size. A large family buys no discount on its first
    discovery; it only earns a longer runway once one is established.
    """
    if declared_cells < 1 or m_annual < 1:
        raise ValueError("declared_cells and m_annual must be positive")
    if declared_cells > m_annual:
        raise ValueError("a family cannot declare more cells than the annual budget")
    if not 0.0 < q_global < 1.0:
        raise ValueError("q_global must be in (0, 1)")
    return q_global * declared_cells / m_annual


@dataclass(frozen=True)
class Discovery:
    """One cell's outcome under an FDR procedure."""

    index: int  # position in the input sequence
    p_value: float
    threshold: float  # the critical value it was compared against
    rejected: bool


def step_up(
    p_values: Sequence[float],
    *,
    declared_cells: int,
    q: float,
    procedure: Procedure,
) -> list[Discovery]:
    """Benjamini-Hochberg / Benjamini-Yekutieli step-up over a family.

    ``declared_cells`` — NOT ``len(p_values)`` — is the denominator. A family
    that declared 200 cells and ran 50 is corrected for 200; that is what
    makes the declaration binding rather than decorative.

    ``procedure="bh"`` requires a pre-declared dependence-structure argument
    in the family's registration. "It left us more survivors" is explicitly
    not such an argument (amendment 4).
    """
    m = declared_cells
    if m < len(p_values):
        raise ValueError(
            f"ran {len(p_values)} cells but declared only {m}; "
            "amend the family declaration before running more"
        )
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1)")

    scale = by_correction_factor(m) if procedure == "by" else 1.0
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])

    # Largest rank whose p-value clears its step-up threshold; everything at
    # or below that rank is rejected, including cells with larger p-values
    # than some non-rejected neighbour would suggest.
    cutoff_rank = 0
    for position, idx in enumerate(order, start=1):
        if p_values[idx] <= q * position / (m * scale):
            cutoff_rank = position

    out: list[Discovery] = []
    for position, idx in enumerate(order, start=1):
        out.append(
            Discovery(
                index=idx,
                p_value=p_values[idx],
                threshold=q * position / (m * scale),
                rejected=position <= cutoff_rank,
            )
        )
    return sorted(out, key=lambda d: d.index)


def first_discovery_threshold(m_annual: int, q_global: float = DEFAULT_Q_GLOBAL) -> float:
    """The bar any family's most significant cell must clear: q_global / M.

    Exposed because it is the single number that makes the budget mechanism
    legible — and because it is identical across families by construction.
    """
    if m_annual < 1:
        raise ValueError("m_annual must be positive")
    return q_global / m_annual
