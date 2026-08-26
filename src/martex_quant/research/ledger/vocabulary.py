"""Controlled vocabulary for the research ledger.

The historical corpus used 11 informal verdict words in free text (KILLED 46,
noise 27, SIGNAL 13, REJECTED 13, ELIGIBLE 7, CANDIDATE 7, INCONCLUSIVE 4,
VALIDATED 2, CONFIRMED 2, SURVIVED 1, DATA-BLOCKED 1). Those words carried
real distinctions — "noise" and "KILLED" are not the same event, and
"ELIGIBLE" and "VALIDATED" sat at different evidence levels — so the
vocabulary here preserves them rather than collapsing them to pass/fail.

``HISTORICAL_VERDICT_ALIASES`` maps the free text found in the committed
documents onto these terms. It is a LABELLING map: it never changes what a
document says, only how the index reads it.
"""

from __future__ import annotations

from enum import StrEnum


class Grade(StrEnum):
    """What kind of claim a trial makes.

    The distinction drives which inferential structure applies: INFO claims
    get FDR within a family, STRATEGY claims get DSR over a selection set.
    """

    INFO = "info"  # a claim about a relationship
    STRATEGY = "strategy"  # a claim about a tradable return stream
    AMBIGUOUS = "ambiguous"  # record unclear; counted into every burden


class Protocol(StrEnum):
    EXPLORATORY = "exploratory"
    CONFIRMATORY = "confirmatory"
    REPLICATION = "replication"
    STRESS = "stress"


class Verdict(StrEnum):
    """Outcome terms, preserving the historical distinctions."""

    NOISE = "noise"  # CI included zero; no effect detected
    SIGNAL = "signal"  # CI excluded zero at the info level
    KILLED = "killed"  # tested and rejected against its pre-registered bar
    REJECTED = "rejected"  # rejected at the strategy grade
    CANDIDATE = "candidate"  # passed its bars, not yet deployed
    ELIGIBLE = "eligible"  # cleared for a paper account
    VALIDATED = "validated"  # cleared the absolute DSR bar
    SURVIVED = "survived"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    INCONCLUSIVE = "inconclusive"
    DATA_BLOCKED = "data_blocked"  # registered but unrunnable; H54
    NOT_ELIGIBLE = "not_eligible"  # passed some bars, failed a gating one


class Maturity(StrEnum):
    """L0-L7 from the MI spec. Assigned by the procedure that produced a
    result, never by judgement of how good it looks."""

    L0_IDEA = "L0"
    L1_EXPLORATORY = "L1"
    L2_PREREGISTERED = "L2"
    L3_INITIAL_EVIDENCE = "L3"
    L4_OUT_OF_SAMPLE = "L4"
    L5_REPLICATED = "L5"
    L6_STRESS_TESTED = "L6"
    L7_STRATEGY_RELEVANT = "L7"


# The maximum maturity each protocol can produce on its own. Exploratory work
# can never reach a verdict above L1 no matter how good it looks; that is the
# wall, expressed as data rather than as a convention.
PROTOCOL_MATURITY_CEILING: dict[Protocol, Maturity] = {
    Protocol.EXPLORATORY: Maturity.L1_EXPLORATORY,
    Protocol.CONFIRMATORY: Maturity.L4_OUT_OF_SAMPLE,
    Protocol.REPLICATION: Maturity.L5_REPLICATED,
    Protocol.STRESS: Maturity.L6_STRESS_TESTED,
}

_MATURITY_ORDER: tuple[Maturity, ...] = (
    Maturity.L0_IDEA,
    Maturity.L1_EXPLORATORY,
    Maturity.L2_PREREGISTERED,
    Maturity.L3_INITIAL_EVIDENCE,
    Maturity.L4_OUT_OF_SAMPLE,
    Maturity.L5_REPLICATED,
    Maturity.L6_STRESS_TESTED,
    Maturity.L7_STRATEGY_RELEVANT,
)


def maturity_rank(level: Maturity) -> int:
    return _MATURITY_ORDER.index(level)


def exceeds_ceiling(protocol: Protocol, level: Maturity) -> bool:
    """True when a trial claims more maturity than its protocol can produce."""
    return maturity_rank(level) > maturity_rank(PROTOCOL_MATURITY_CEILING[protocol])


# Free text found in the committed ledger and hypothesis documents, mapped to
# the controlled terms. Adding an entry here is a labelling decision and must
# be justified by the document it reads.
HISTORICAL_VERDICT_ALIASES: dict[str, Verdict] = {
    "noise": Verdict.NOISE,
    "signal": Verdict.SIGNAL,
    "killed": Verdict.KILLED,
    "rejected": Verdict.REJECTED,
    "candidate": Verdict.CANDIDATE,
    "eligible": Verdict.ELIGIBLE,
    "validated": Verdict.VALIDATED,
    "survived": Verdict.SURVIVED,
    "confirmed": Verdict.CONFIRMED,
    "superseded": Verdict.SUPERSEDED,
    "inconclusive": Verdict.INCONCLUSIVE,
    "data-blocked": Verdict.DATA_BLOCKED,
    "data_blocked": Verdict.DATA_BLOCKED,
    "not eligible": Verdict.NOT_ELIGIBLE,
    "not_eligible": Verdict.NOT_ELIGIBLE,
}
