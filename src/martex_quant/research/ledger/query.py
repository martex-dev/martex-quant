"""Stage 6: asking the ledger questions, including the graveyard.

The single most valuable question a research lab can answer about itself is
**"have we already tested this?"** — because the alternative is rediscovering
the same dead end and, worse, counting it as a fresh result. The corpus has
120 trials and 46 recorded kills; without search that knowledge decays into
folklore.

Everything here reads the ledger. Nothing mutates it: the source of truth is
the committed document, and a query that could change what it found would be
a contradiction in terms.
"""

from __future__ import annotations

from dataclasses import dataclass

from martex_quant.research.ledger.records import Ledger, Trial
from martex_quant.research.ledger.vocabulary import Grade, Verdict

# Verdicts that mean "this idea was tried and did not survive". Kept explicit
# rather than inferred: "noise" (no effect detected) and "killed" (failed its
# pre-registered bar) are different events, and both belong in the graveyard.
DEAD_VERDICTS: frozenset[Verdict] = frozenset(
    {Verdict.KILLED, Verdict.REJECTED, Verdict.NOISE, Verdict.NOT_ELIGIBLE}
)

# Verdicts that mean "this survived its bar at some level".
LIVE_VERDICTS: frozenset[Verdict] = frozenset(
    {
        Verdict.SIGNAL,
        Verdict.CANDIDATE,
        Verdict.ELIGIBLE,
        Verdict.VALIDATED,
        Verdict.SURVIVED,
        Verdict.CONFIRMED,
    }
)


@dataclass(frozen=True)
class SearchHit:
    trial: Trial
    matched_on: str  # which field the query matched, so a hit is explainable

    def describe(self) -> str:
        t = self.trial
        dsr = f", DSR {t.dsr:.3f}@{t.dsr_n_trials}" if t.dsr is not None else ""
        return f"{t.hypothesis} [{t.family}] {t.verdict.value}{dsr} — matched {self.matched_on}"


def search(ledger: Ledger, term: str) -> list[SearchHit]:
    """Free-text search across hypothesis, family, evidence and notes.

    Case-insensitive substring matching, deliberately. A researcher asking
    "have we tried funding?" should not have to know whether the ledger spells
    it "funding", "Funding rate" or "fundingRate".
    """
    needle = term.strip().lower()
    if not needle:
        return []
    hits: list[SearchHit] = []
    for trial in ledger.trials:
        for field, value in (
            ("hypothesis", trial.hypothesis),
            ("family", trial.family),
            ("evidence", trial.evidence),
            ("notes", trial.notes),
        ):
            if needle in value.lower():
                hits.append(SearchHit(trial=trial, matched_on=field))
                break
    return hits


def already_tested(ledger: Ledger, term: str) -> bool:
    """The question worth asking before every new idea."""
    return bool(search(ledger, term))


def graveyard(ledger: Ledger) -> list[Trial]:
    """Every trial that was tried and did not survive.

    A killed hypothesis stays permanently visible. That is the point: the
    ledger's honesty is the project's only real asset, and a graveyard you
    cannot search is a graveyard that gets re-dug.
    """
    return [t for t in ledger.trials if t.verdict in DEAD_VERDICTS]


def survivors(ledger: Ledger) -> list[Trial]:
    return [t for t in ledger.trials if t.verdict in LIVE_VERDICTS]


def by_family(ledger: Ledger, family_prefix: str) -> list[Trial]:
    """Trials in a family or any of its descendants."""
    return ledger.family_trials(family_prefix)


def kill_rate(ledger: Ledger, family_prefix: str | None = None) -> float:
    """Share of trials in scope that died. The lab's honesty metric.

    A lab with a low kill rate is not finding more truth; it is either testing
    only safe ideas or failing to kill bad ones.
    """
    scope = by_family(ledger, family_prefix) if family_prefix else ledger.trials
    if not scope:
        return 0.0
    return sum(1 for t in scope if t.verdict in DEAD_VERDICTS) / len(scope)


def strategy_grade_with_dsr(ledger: Ledger) -> list[Trial]:
    """Strategy trials carrying a published DSR, newest ledger position first.

    Each keeps the n_trials it was actually deflated against — 65, 104, 107 —
    never today's total. Comparing these figures across eras is invalid
    without equalising n_trials, which is a recomputation.
    """
    return sorted(
        (t for t in ledger.trials if t.grade is Grade.STRATEGY and t.dsr is not None),
        key=lambda t: t.trial_id,
        reverse=True,
    )


def contradictions(ledger: Ledger) -> list[tuple[Trial, Trial]]:
    """Pairs in the same family with opposing verdicts.

    A conflict is not automatically an error — it can be a horizon, universe
    or regime difference — but it must be visible rather than averaged away.
    Reported as pairs for a human to adjudicate; the lab does not resolve them.
    """
    out: list[tuple[Trial, Trial]] = []
    live = [t for t in ledger.trials if t.verdict in LIVE_VERDICTS]
    dead = [t for t in ledger.trials if t.verdict in DEAD_VERDICTS]
    for a in live:
        for b in dead:
            if a.family == b.family and a.hypothesis.split("#")[0] != b.hypothesis.split("#")[0]:
                out.append((a, b))
    return out


def summarise(ledger: Ledger) -> str:
    """A plain-language state of the ledger."""
    dead, alive = len(graveyard(ledger)), len(survivors(ledger))
    return "\n".join(
        [
            f"trials registered : {ledger.n_registered}  (run {ledger.n_run})",
            f"families          : {len(ledger.families)}",
            f"died              : {dead}",
            f"survived          : {alive}",
            f"kill rate         : {kill_rate(ledger):.0%}",
            f"strategy w/ DSR   : {len(strategy_grade_with_dsr(ledger))}",
        ]
    )
