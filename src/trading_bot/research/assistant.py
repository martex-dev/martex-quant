"""Stage 13: the research assistant — rules enforcement before a test runs.

The project's operating rules live in CLAUDE.md and in PROJECT_MEMORY's
lessons. They are followed by memory, which is exactly the mechanism that
fails on a tired evening at trial 130. This module turns the load-bearing
ones into code that runs BEFORE a hypothesis does.

**It can only object. It never approves.** There is deliberately no
``approved`` flag and no ``passed`` boolean anywhere here — a checker that
returns APPROVED invites being read as authorization, and a clean run means
only "none of the mechanical rules were violated", which is a far weaker
claim than "this is worth running". Judgement stays human.

What it checks, and where each rule comes from:

* **Re-testing a killed idea** (CLAUDE.md: never without a new spec and a
  STATED REASON). The reason must be present and substantive.
* **Contradicting a settled finding** — H36 killed the short leg, so a
  proposal that predicts SHORT is contradicting a result rather than
  extending one, and must say so deliberately.
* **The ledger cost** — every trial raises the deflated-Sharpe hurdle for
  every future claim. The proposal must state its count, and the cost is
  computed rather than asserted.
* **The equal-weight baseline** (new standing rule from H58): any model that
  learns weights must be raced against not learning them. H58 is why — the
  unweighted composite beat every learned variant.
* **The incremental bar** (CLAUDE.md): new features must beat the DEPLOYED
  system, not zero.
* **Pre-registration** — bars committed before results exist.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Severity(StrEnum):
    BLOCKING = "BLOCKING"  # the proposal violates a standing rule
    CAUTION = "CAUTION"  # legitimate, but a known trap is nearby


@dataclass(frozen=True)
class Objection:
    severity: Severity
    rule: str
    detail: str
    source: str  # where the rule is written down

    def describe(self) -> str:
        return f"[{self.severity}] {self.rule}\n    {self.detail}\n    rule: {self.source}"


@dataclass(frozen=True)
class Proposal:
    """A hypothesis someone wants to run, before it runs."""

    name: str
    claim: str
    trial_count: int
    #: Hypotheses this restates or revisits, by ledger name (e.g. "H33").
    revisits: tuple[str, ...] = ()
    #: Required whenever ``revisits`` is non-empty.
    reason_for_revisiting: str = ""
    #: Settled findings this proposal contradicts, if any.
    contradicts: tuple[str, ...] = ()
    #: Does the design learn weights/parameters from data?
    learns_parameters: bool = False
    #: Is an unweighted / no-fitting baseline among the declared cells?
    declares_equal_weight_baseline: bool = False
    #: What it must beat. "zero" is the classic mistake.
    beats: str = ""
    #: Path to the committed pre-registration.
    preregistration: str = ""
    #: Grade being claimed: "info" or "strategy".
    grade: str = "info"


@dataclass
class Review:
    proposal: Proposal
    ledger_before: int
    objections: list[Objection] = field(default_factory=list)

    @property
    def ledger_after(self) -> int:
        return self.ledger_before + self.proposal.trial_count

    @property
    def blocking(self) -> list[Objection]:
        return [o for o in self.objections if o.severity is Severity.BLOCKING]

    def describe(self) -> str:
        lines = [
            f"REVIEW: {self.proposal.name}",
            f"  ledger {self.ledger_before} -> {self.ledger_after} (+{self.proposal.trial_count})",
            "",
        ]
        if not self.objections:
            lines.append("  No standing rule was violated.")
            lines.append("  That is NOT approval — it means the mechanical checks found")
            lines.append("  nothing. Whether this is worth running is a human judgement.")
            return "\n".join(lines)
        for objection in self.objections:
            lines.append(objection.describe())
            lines.append("")
        n = len(self.blocking)
        lines.append(
            f"  {n} blocking objection(s). Resolve them in the registration, not in the analysis."
            if n
            else "  No blocking objections; cautions above are for the author to weigh."
        )
        return "\n".join(lines)


CLAUDE_MD = "CLAUDE.md — non-negotiable operating rules"
MEMORY = "PROJECT_MEMORY.md — hypothesis ledger"


def killed_hypotheses(ledger_path: Path) -> set[str]:
    """Names the ledger records as killed, expanded across ranges.

    Entries are written as "H44-H50" or "H52-H57" as well as "H58", so a
    literal match would miss most of the corpus — the exact way a duplicate
    would slip through unnoticed.
    """
    payload = tomllib.loads(ledger_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for entry in payload.get("entries", []):
        if entry.get("verdict") != "killed":
            continue
        name = str(entry.get("hypothesis", ""))
        out.update(_expand(name))
    return out


def _expand(name: str) -> set[str]:
    """'H44-H50' -> {H44..H50}; 'H58' -> {H58}; 'PHASE3' -> {PHASE3}."""
    if "-" not in name:
        return {name}
    left, _, right = name.partition("-")
    if not (left.startswith("H") and right.startswith("H")):
        return {name}
    try:
        lo, hi = int(left[1:]), int(right[1:])
    except ValueError:
        return {name}
    return {f"H{n}" for n in range(lo, hi + 1)}


def review(proposal: Proposal, *, ledger_total: int, killed: set[str]) -> Review:
    """Check a proposal against the standing rules. Objections only."""
    result = Review(proposal=proposal, ledger_before=ledger_total)
    add = result.objections.append

    if not proposal.preregistration:
        add(
            Objection(
                Severity.BLOCKING,
                "no pre-registration",
                "Bars must be committed BEFORE any result exists. Without a "
                "committed document there is nothing stopping the bars moving "
                "to meet the result.",
                CLAUDE_MD,
            )
        )

    if proposal.trial_count < 1:
        add(
            Objection(
                Severity.BLOCKING,
                "trial count not declared",
                "Every trial counts against the ledger, including variants and "
                "descriptive horizons. A proposal claiming zero trials is either "
                "not a test or is not counting honestly.",
                CLAUDE_MD,
            )
        )

    revisited_kills = [h for h in proposal.revisits if h in killed]
    if revisited_kills and len(proposal.reason_for_revisiting.split()) < 5:
        add(
            Objection(
                Severity.BLOCKING,
                f"re-tests killed hypothesis {', '.join(revisited_kills)}",
                "A killed idea may only be re-tested with a NEW pre-registered "
                "spec and a STATED REASON. No substantive reason was given.",
                CLAUDE_MD,
            )
        )
    elif revisited_kills:
        add(
            Objection(
                Severity.CAUTION,
                f"re-tests killed hypothesis {', '.join(revisited_kills)}",
                f"Reason given: {proposal.reason_for_revisiting!r}. Permitted, but "
                "the registration must say what is DIFFERENT this time, not just "
                "why the idea is appealing.",
                CLAUDE_MD,
            )
        )

    for finding in proposal.contradicts:
        add(
            Objection(
                Severity.CAUTION,
                f"contradicts settled finding {finding}",
                "Contradicting a result is allowed and sometimes the point, but "
                "it must be deliberate and named in the registration — not "
                "discovered afterwards when the numbers disagree.",
                MEMORY,
            )
        )

    if proposal.learns_parameters and not proposal.declares_equal_weight_baseline:
        add(
            Objection(
                Severity.BLOCKING,
                "no equal-weight baseline declared",
                "Any design that LEARNS weights must race against not learning "
                "them. H58 is why this is a rule and not a suggestion: the "
                "unweighted composite (+2.79%, CI clear) beat every learned "
                "variant, all of which were noise.",
                "PROJECT_MEMORY.md — meta-finding 4",
            )
        )

    if not proposal.beats:
        add(
            Objection(
                Severity.BLOCKING,
                "no incremental bar declared",
                "State what this must beat. New features must beat the DEPLOYED system, not zero.",
                CLAUDE_MD,
            )
        )
    elif proposal.beats.strip().lower() in {"zero", "0", "nothing", "random"}:
        add(
            Objection(
                Severity.BLOCKING,
                "incremental bar is zero",
                f"Declared bar is {proposal.beats!r}. Beating zero is not a bar — "
                "the deployed system already beats zero. This is the single most "
                "common way a dead idea survives review.",
                CLAUDE_MD,
            )
        )

    if proposal.grade == "strategy":
        add(
            Objection(
                Severity.CAUTION,
                "strategy grade claimed",
                "Strategy grade requires the event-driven engine as source of "
                "truth, full costs, and DSR against the ledger total at the time "
                f"({result.ledger_after} after this proposal). Vectorized "
                "screening is pre-engine only.",
                CLAUDE_MD,
            )
        )

    return result
