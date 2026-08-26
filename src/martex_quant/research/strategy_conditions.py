"""Stage 10: when does a strategy work? — the highest-risk analysis here.

This is subgroup analysis on a return stream that was ALREADY selected for
good overall performance, using conditions chosen after seeing the strategy.
The false-discovery base rate is the worst in the lab, so the approved
accounting design constrains it harder than anything else, and those
constraints are enforced in code rather than left to memory:

1. **Effective sample size is independent regime EPISODES, not days.** A
   single 26-day drawdown is n≈1, however many rows it contains. Consecutive
   days in one regime are one observation of that regime.
2. **No p-values until minimum episode rules are pre-registered.** Output is
   DESCRIPTIVE ONLY. There is no function here that returns significance.
3. **Maturity ceiling L1.** Nothing here can promote a finding.
4. **A state filter is a NEW STRATEGY.** It cannot reach the live book
   through this analysis; it must pass the full validation path as its own
   pre-registered spec.
5. **The drawdown guardrail.** PROJECT_STATE records that any analysis
   touching 2026-07-12..2026-08-10 must be pre-registered BEFORE the window
   is examined. ``guard_drawdown_window`` refuses that window unless the
   caller passes an explicit registration reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import polars as pl

# The open, unexplained paper drawdown. Recorded in PROJECT_STATE so it cannot
# later be presented as a discovery.
GUARDED_WINDOW = (datetime(2026, 7, 12, tzinfo=UTC), datetime(2026, 8, 10, tzinfo=UTC))

MATURITY_CEILING = "L1"  # descriptive observation, always


class PreRegistrationRequired(Exception):
    """Raised when the guarded drawdown window is examined without a
    pre-registered hypothesis reference."""


@dataclass(frozen=True)
class Episode:
    """One contiguous stretch during which a condition held."""

    start: datetime
    end: datetime
    days: int
    mean_return: float


@dataclass(frozen=True)
class ConditionalPerformance:
    """Strategy performance under one market condition. DESCRIPTIVE ONLY.

    Carries no p-value and no verdict by construction. ``episodes`` is the
    number that matters — ``days`` is included only because omitting it would
    invite someone to recompute it and treat it as the sample size.
    """

    condition: str
    episodes: int
    days: int
    mean_return_on: float
    mean_return_off: float

    @property
    def difference(self) -> float:
        return self.mean_return_on - self.mean_return_off

    @property
    def too_few_episodes(self) -> bool:
        """Below ten independent episodes, the design says report descriptively
        and attach no inference at all. The threshold itself is still awaiting
        pre-registration; ten is the design's proposed value, used here as a
        WARNING line rather than a decision rule."""
        return self.episodes < 10

    def describe(self) -> str:
        warning = (
            f"  ** only {self.episodes} episode(s) — far too few for inference; read as anecdote **"
            if self.too_few_episodes
            else ""
        )
        return (
            f"{self.condition}: {self.episodes} episodes over {self.days} days\n"
            f"  strategy return  on: {self.mean_return_on:+.4%}   "
            f"off: {self.mean_return_off:+.4%}   diff: {self.difference:+.4%}\n"
            f"  DESCRIPTIVE ONLY (maturity {MATURITY_CEILING}); no significance claimed"
            + (f"\n{warning}" if warning else "")
        )


def guard_drawdown_window(
    start: datetime, end: datetime, *, preregistration: str | None = None
) -> None:
    """Refuse the guarded window unless a registration is cited.

    The guardrail exists because the 2026-07 drawdown is exactly the kind of
    material that invites post-hoc explanation, and 26 daily marks is n≈1.
    """
    guard_start, guard_end = GUARDED_WINDOW
    overlaps = start <= guard_end and end >= guard_start
    if overlaps and not preregistration:
        raise PreRegistrationRequired(
            f"the window {start:%Y-%m-%d}..{end:%Y-%m-%d} overlaps the guarded paper "
            f"drawdown ({guard_start:%Y-%m-%d}..{guard_end:%Y-%m-%d}). "
            "Pre-register a hypothesis before examining it and pass its reference "
            "as `preregistration=`; 26 marks is one episode, not a sample."
        )


def find_episodes(frame: pl.DataFrame, condition: pl.Expr, *, return_column: str) -> list[Episode]:
    """Contiguous runs where the condition holds.

    THE core method of this stage. Counting days would report a 26-day
    drawdown as 26 observations; counting episodes reports it as one, which
    is what it is.
    """
    tagged = frame.sort("day").with_columns(on=condition.fill_null(False))
    rows = tagged.select("day", "on", return_column).iter_rows(named=True)

    episodes: list[Episode] = []
    run_start: datetime | None = None
    run_days = 0
    run_sum = 0.0
    previous: datetime | None = None

    for row in rows:
        if row["on"]:
            if run_start is None:
                run_start, run_days, run_sum = row["day"], 0, 0.0
            run_days += 1
            run_sum += float(row[return_column] or 0.0)
            previous = row["day"]
        elif run_start is not None:
            assert previous is not None
            episodes.append(Episode(run_start, previous, run_days, run_sum / max(run_days, 1)))
            run_start = None
    if run_start is not None and previous is not None:
        episodes.append(Episode(run_start, previous, run_days, run_sum / max(run_days, 1)))
    return episodes


def conditional_performance(
    frame: pl.DataFrame,
    condition: pl.Expr,
    label: str,
    *,
    return_column: str = "strategy_return",
    preregistration: str | None = None,
) -> ConditionalPerformance:
    """Strategy performance on/off a condition, counted in EPISODES.

    Refuses the guarded drawdown window without a registration reference.
    """
    if frame.height:
        span = frame["day"]
        guard_drawdown_window(span.min(), span.max(), preregistration=preregistration)  # type: ignore[arg-type]

    episodes = find_episodes(frame, condition, return_column=return_column)
    tagged = frame.with_columns(on=condition.fill_null(False))
    on = tagged.filter(pl.col("on"))[return_column].mean()
    off = tagged.filter(~pl.col("on"))[return_column].mean()
    return ConditionalPerformance(
        condition=label,
        episodes=len(episodes),
        days=sum(e.days for e in episodes),
        mean_return_on=on if isinstance(on, float) else 0.0,
        mean_return_off=off if isinstance(off, float) else 0.0,
    )


def performance_matrix(
    frame: pl.DataFrame,
    conditions: dict[str, pl.Expr],
    *,
    return_column: str = "strategy_return",
    preregistration: str | None = None,
) -> list[ConditionalPerformance]:
    """A strategy x market-state row per condition. Descriptive throughout."""
    return [
        conditional_performance(
            frame, expr, label, return_column=return_column, preregistration=preregistration
        )
        for label, expr in conditions.items()
    ]


def render(matrix: list[ConditionalPerformance]) -> str:
    header = (
        "STRATEGY x MARKET STATE — DESCRIPTIVE ONLY\n"
        "Nothing below is a finding. A state filter derived from this table is a\n"
        "NEW STRATEGY and must pass the full validation path as its own spec.\n"
    )
    return header + "\n" + "\n\n".join(row.describe() for row in matrix)
