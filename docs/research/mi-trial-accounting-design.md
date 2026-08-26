# Trial Accounting & Multiple-Testing Design (MI Lab Layer 2)

Date: 2026-08-10. Status: **APPROVED with amendments 1–9 (2026-08-10).
Gate closed; Layer 1 may proceed.** One later amendment (10, §2) is
PROPOSED and awaiting an owner decision; it does not block Layer 1.
Status header reconciled 2026-08-26 — it still read "DESIGN — for review"
long after §11 recorded the approval, which left PROJECT_STATE listing
this gate as an open next action it no longer was.
Prerequisite for: MI Lab Layers 1–4.
Companion documents: docs/research/market-intelligence-lab-audit.md,
PROJECT_MEMORY.md (the 120-trial ledger), CLAUDE.md (standing rules).

This document defines the statistical semantics of the research ledger
before any high-volume testing capability exists. It answers one
question: **when the lab has run 10,000 tests, what does a surviving
finding actually mean?**

---

## 0. The constraint set (approved 2026-08-10)

1. Hierarchical research families + a hard exploratory/confirmatory wall.
2. **No cap on discovery rate.** Exploration may be broad and high-volume.
3. Exploratory trials enter the permanent global research history.
4. The family hierarchy **must not be used to hide exploratory trials
   from the overall false-discovery burden.**
5. Six records must be independently distinguishable: global history,
   family, exploratory, confirmatory, replication, strategy-relevant.
6. No failed experiment may disappear from any record.
7. MI experiments must NOT simply be appended to the existing DSR
   calculation without determining the correct semantics first.

Constraints 2 and 4 are in tension: unlimited testing that costs nothing
is dredging. The resolution proposed here is:

> **Volume is charged through the error budget, not through a rate cap.**

You may run ten thousand cells. Each one makes every cell in that family
need a stronger effect to survive. Nothing is blocked; everything is
priced.

---

## 1. Why the current rule cannot simply be extended

Current practice: one number, DSR, with `n_trials` = every trial ever
run (120 today). `expected_max_sharpe(N)` is the expected maximum Sharpe
among N *unskilled* trials — it models **the maximum of a selection**.

Two problems appear at scale:

**(a) It is the wrong estimator for info-level tests.** A block-bootstrap
CI on "does extreme funding predict lower returns" is not a Sharpe ratio
and was never a candidate for deployment. Folding it into the N of a
maximum-Sharpe statistic is a category error. It is currently harmless
(and admirably conservative) because N is small.

**(b) At scale it becomes self-defeating.** Counting info cells into a
strategy's DSR means a productive MI lab mechanically prevents its own
strategies from ever validating:

| Selection-set N | E[max Sharpe]/σ | Hurdle vs today |
|---|---|---|
| 8 | 1.459 | ×0.56 |
| 20 | 1.901 | ×0.73 |
| 40 | 2.189 | ×0.84 |
| 120 (today, global) | 2.594 | ×1.00 |
| 10,000 | 3.861 | ×1.49 |

An undisciplined merge of MI into the existing counter is therefore not
conservative — it is incoherent. The fix is not to lower the bar. It is
to apply **the right correction to the right claim**, and to add a
second, genuinely global mechanism (§4) so that exploration volume is
still charged.

---

## 2. Definitions

**Trial.** One tuple `(hypothesis, predictor, outcome, horizon,
conditioning, data window, methodology, data vintage)` whose result was
*produced*. A computed-but-unread cell inside an automated sweep **is a
trial** — the sweep's selection acts on all cells regardless of whether
a human read them. This closes the "I only looked at three of them"
loophole.

**Amendment 10 — PROPOSED 2026-08-26, NOT YET RATIFIED. Description
versus selection.** Surfaced by an outside contributor proposal (see
docs/research/bounded-search-proposal-response.md §5), which noted that
this document's trial rule and `docs/research/owncap-sizing.md` appear to
contradict each other: owncap-sizing swept five leverage values over the
43a book, published a metric table per value, and declared **0 new ledger
trials**. Proposed reconciliation:

> A sweep that publishes its **whole** surface and selects no operating
> point on statistical grounds costs no trials — it is a published
> trade-off table, and the choice made from it is a human policy
> decision. The moment a winner is picked **on a metric** and carried
> forward as a claim, every cell it beat has entered the selection set
> and every cell is a trial.
>
> **Selection against a metric is what consumes alpha. Description does
> not.**

This is offered as the *reason* the computed-but-unread rule above is
correct, not as an exception to it. Guard, if ratified: the exemption
applies only when the full surface is published and no cell is advanced
as a claim. "We only meant it descriptively," asserted after seeing which
cell won, is selection.

**Owner decision required.** Until ratified, the unqualified rule above
governs and every evaluated cell is a trial. Recorded here rather than
applied, because a change to what counts as a trial is a methodological
decision and this document's own §4.2 precedent is that such decisions
are made deliberately and never inferred.

**Family.** A declared, hierarchical region of hypothesis space with a
**fixed cell count declared at registration**, e.g.
`MI.derivatives.funding.extremes`. Families nest; the path is the id.

**Cell count `m_k`.** The number of cells a family *declares*, not the
number it runs. Declaring a 20-feature × 10-horizon grid and running 50
cells still costs 200. This closes the "declare big, run small, claim
the rest were cancelled" loophole.

**Selection set.** The set of candidates whose test statistics were
compared with each other in order to pick a winner. This — not the
global count — is the N that belongs in a maximum-statistic correction.
Selection sets are permanent and cumulative: a strategy family's set
includes every configuration ever Sharpe-ranked within it, across all
sessions.

**Grade.** `INFO` (a claim about a relationship) or `STRATEGY` (a claim
about a tradable return stream). Different claims, different estimators.

**Protocol.** `EXPLORATORY` | `CONFIRMATORY` | `REPLICATION` | `STRESS`.

**Maturity.** L0–L7 per MI spec §41. Maturity is *assigned by the
procedure that produced it*, never by judgement of how good a result
looks.

---

## 3. The six records (constraint 5)

All six are views over one append-only trial table. None can be
decremented; deletion is impossible by construction (§7).

| Record | Definition | Statistical role |
|---|---|---|
| **Global history `G`** | Every trial ever, monotonic id | **Audit, not inference.** "Have we tested this?", graveyard search, reproducibility. Never used directly as a correction parameter. |
| **Family `F_k`** | Trials in family k, with declared `m_k` | The FDR unit. Carries the error budget. |
| **Exploratory `E`** | Protocol = EXPLORATORY | Charged against the family budget; **can never produce a finding above L1.** |
| **Confirmatory `C`** | Protocol = CONFIRMATORY, pre-registered | The only protocol that can promote past L2. Reserved-window data. |
| **Replication `R`** | Protocol = REPLICATION | Counted as attempted/survived fractions. No alpha spend (§5.3). |
| **Strategy-relevant `S`** | Grade = STRATEGY | The DSR selection sets. Disjoint from INFO cells. |

`G` is deliberately demoted from "the DSR parameter" to "the audit
record". That is the single most important change in this design, and it
is what makes constraints 2 and 4 co-satisfiable.

---

## 4. Inferential structure per claim type

### 4.1 INFO claims → hierarchical FDR with a globally allocated budget

An info claim is `E[outcome | condition] ≠ E[outcome | ¬condition]`.
These arrive in large, correlated families.

- **Within family k:** Benjamini–Hochberg at level `q_k` over the
  family's `m_k` declared cells.
- **Dependence:** cells within a family overlap heavily (shared bars,
  nested horizons, correlated features). Default to **Benjamini–Yekutieli**,
  valid under arbitrary dependence, unless positive dependence (PRDS) is
  explicitly argued in the registration. The cost is real and should be
  budgeted for:

  | m_k | BY factor c(m) | Effective strictness vs BH |
  |---|---|---|
  | 10 | 2.93 | ×2.9 |
  | 50 | 4.50 | ×4.5 |
  | 200 | 5.88 | ×5.9 |
  | 1,000 | 7.49 | ×7.5 |
  | 10,000 | 9.79 | ×9.8 |

- **Global allocation (this is the mechanism that satisfies constraint 4):**
  the global FDR budget `q_global` (proposed: 0.10) is split across
  families in proportion to declared size:

  ```
  q_k = q_global × m_k / M        where M = Σ m_k over all declared families
  ```

  This is a conservative (Bonferroni-style) split of the FDR budget; it
  guarantees global FDR ≤ `q_global`.

**Why this is exactly the property the constraint asks for.** Under
proportional allocation, the threshold the *most significant* cell in
any family must clear is `q_k / m_k = q_global / M` — **identical for
every family, regardless of family size.** Verified numerically:

| Family cells `m_k` | Share of M | `q_k` | Threshold for its top cell |
|---|---|---|---|
| 20 | 0.2% | 0.0002 | p ≤ 1.00e-05 |
| 100 | 1.0% | 0.0010 | p ≤ 1.00e-05 |
| 1,000 | 10.0% | 0.0100 | p ≤ 1.00e-05 |
| 8,000 | 80.0% | 0.0800 | p ≤ 1.00e-05 |

(with `q_global` = 0.10, M = 10,000)

So: **a large family buys no discount on its first discovery.** It only
earns a longer runway once a genuine effect is established. Exploring
more raises `M`, which tightens `q_global/M` for *everyone* — including
the explorer. Volume is charged globally and cannot be hidden inside a
family. Constraint 4 is satisfied mechanically, not by policy.

*Refinement to consider later:* Benjamini–Bogomolov selective inference
on families is more powerful than the proportional split when only some
families are reported. Deferred — the conservative split is the correct
starting point, and power is not our scarce resource.

**Amendment 2 — annual active burden, permanent lifetime record.**
`M` has two forms, both always reported, never substitutable:

- **`M_annual`** — declared cell count for the current research period.
  This is the budget denominator used for `q_k` allocation.
- **`M_lifetime`** — cumulative declared cells across every period since
  project start. Never reset, never decremented.

The annual reset applies **only** to the active allocation denominator.
It does not erase, discount, or hide any historical research volume:
`M_lifetime` and `|G|` both continue monotonically across period
boundaries, and every report that prints `M_annual` must print
`M_lifetime` beside it. A period boundary is a budgeting event, not an
amnesty.

**Amendment 3 — `q_global` is a methodological parameter, not a truth.**
Initial value **0.10**. It is configurable and versioned, and its value
is recorded with every result computed under it. Any change is a
methodological decision requiring its own pre-registration and stated
reasoning. It may never be re-tuned against historical results, and a
result may never be recomputed under a different `q_global` in order to
change its verdict.

**Amendment 4 — BY is the default, and the exit is justified in advance.**
Benjamini–Yekutieli is the default procedure for every family. Switching
a family to BH requires a **pre-defined methodological justification
about that family's dependence structure**, written into the family's
registration before results exist. "BY left us with fewer surviving
discoveries" is explicitly not a valid reason and must be rejected if
offered.

### 4.2 STRATEGY claims → the existing bar stands; `DSR_selection` is a diagnostic only

**AMENDED 2026-08-10 (amendment 1). The draft of this section proposed
replacing the global-N DSR bar with a selection-set-N bar. That proposal
was REJECTED. It is recorded here rather than deleted, because a
rejected methodological proposal is part of the research record.**

The operative rule is unchanged from current practice:

- **The strategy-grade acceptance criterion remains `DSR_global` ≥ 0.95**,
  with N = the global trial count, exactly as the 120-trial ledger has
  always computed it. Nothing in the MI Lab weakens it.
- **`DSR_global` must remain permanently visible** on every strategy
  verdict, ledger row, and report.
- **`DSR_selection`** (N = size of the selection set, §2) may be computed
  and reported **as an additional diagnostic**. It has no gating power.
  Its purpose is to make visible *how much* of a spec's hurdle comes from
  the global research burden versus its own selection — useful
  information, not a licence.
- If the strategy-grade threshold is ever to change, that is a
  **separate methodological decision requiring its own pre-registration**,
  decided on methodological grounds and never tuned against historical
  results.

Consequence, stated plainly: as `|G|` grows, the strategy-grade bar gets
harder, and MI exploration contributes to that. This is accepted
deliberately. It is the price of not letting a discovery engine
relax the standard that validated the existing book.

**Selection sets are still recorded** — cumulative, permanent, including
abandoned variants — because they are needed for the diagnostic and for
§9's independent-evidence accounting.

### 4.3 REPLICATION → no alpha spend, asymmetric bookkeeping

A replication is a single pre-specified test of an existing claim, not a
search. Correcting it for multiplicity would make replication *harder*
the more you replicate — an inverted incentive.

- No FDR/DSR correction is applied to a replication.
- Every replication attempt is permanently attached to its parent
  finding and reported as `survived / attempted`.
- **A finding's report must display its failed replications adjacent to
  its successful ones.** Cherry-picking is prevented by the report
  template, not by discipline.
- Replications must vary something declared in advance (period,
  universe, venue, methodology, seed) and record which.

### 4.4 STRESS → can only demote

A stress test spends no error budget and confers no significance.
Surviving a stress test does not raise maturity. Failing one demotes the
finding and records the breaking point. Deliberately asymmetric: the
purpose is to find where a result breaks, and a procedure that rewarded
survival would create pressure to design weak stresses.

### 4.5 STRATEGY × MARKET-STATE → the highest-risk category, most constrained

This is subgroup analysis on a return stream that was *already selected
for good overall performance*, using conditioning variables chosen after
seeing the strategy. The false-discovery base rate is the worst in the lab.

Rules:

1. **The effective sample size is the number of independent regime
   episodes, not the number of days.** A single 26-day drawdown is n ≈ 1.
   Every conditional report must state episode count.
2. **Amendment 5 — until minimum episode-count rules are finalized and
   pre-registered, ALL strategy × market-state output is research-level
   observation only.** No p-value is reported, no verdict is issued, and
   **nothing in this category can become strategy-grade automatically**
   by any procedure. Promotion is a human decision requiring a separate
   pre-registered hypothesis.
3. Conditional cells are charged to a declared family like any other
   info cells (§4.1), with `m_k` = states × strategies × horizons declared.
4. **Default maturity ceiling L1.** Promotion above L3 requires regime
   episodes from a reserved window not used in the descriptive pass.
5. **Amendment 6 — a market-state filter is a new strategy.** Any
   strategy modification derived from MI enters the existing full
   research/validation path with no shortcut: pre-registration,
   event-driven engine as source of truth, walk-forward, the standing
   `DSR_global` ≥ 0.95 bar (§4.2), prop-sim, and the incremental
   requirement to beat the deployed system rather than zero.
6. Per PROJECT_STATE.md's guardrail (amendment 8): any analysis touching
   the 2026-07-12 → 2026-08-10 paper drawdown must be pre-registered
   before the window is examined. This guardrail stands until explicitly
   retired in writing.

---

## 4.6 Research volume ≠ independent evidence (amendment 9)

A count of trials is a measure of *effort*, not of *evidence*. Ten
thousand tests over one dataset, one period, and one family of closely
related features are not ten thousand independent pieces of evidence —
they are approximately one, tested many ways.

The system must therefore never report volume alone. Every finding and
every family summary carries a **four-part evidence descriptor**:

| Dimension | What it counts | Why it is not volume |
|---|---|---|
| **Research volume** | trials run (`|G|`, `F_k`) | measures effort and multiple-testing burden |
| **Independent families** | distinct declared families supporting the claim | correlated variants inside one family collapse to ~1 |
| **Independent periods / datasets** | non-overlapping time windows, universes, venues, data sources | the binding constraint in a 9-year single-market history |
| **Replication count** | independent replications attempted / survived | the only dimension that adds genuinely new information |

Rules that follow:

- A finding's strength is described by the descriptor, **never by trial
  count**. "Tested 47 ways" is not a strength claim; it is a burden
  disclosure.
- Two families are counted as independent only if declared independently
  in advance, on stated grounds. Retroactively splitting one family into
  several to inflate this number is prohibited and detectable in the
  registration diff.
- Reports must show the descriptor's weakest dimension prominently. A
  finding with volume 5,000, independent periods 1, replications 0 must
  read as what it is: one observation, examined exhaustively.
- This descriptor is the intended answer to MI spec §32 (discovery
  confidence) — an evidence structure, not a confidence percentage.

---

## 5. The exploratory/confirmatory wall

A label is not a wall. Four mechanisms make it one:

1. **Reserved evaluation windows.** The data layer serves two accessors:
   a research view that physically excludes reserved windows, and a
   confirmatory accessor that requires a registered hypothesis id.
   Exploratory code paths cannot reach reserved data. This is testable —
   and it is a Layer 3/4 acceptance criterion, not an aspiration.
2. **Registration precedes execution, in git.** A confirmatory run
   requires a committed doc containing predictor, outcome, horizons,
   family + declared `m_k`, verdict bars, methodology, and the data
   vintage. The runner refuses to execute against an uncommitted or
   dirty registration.
3. **No relabelling, ever.** An exploratory trial cannot become
   confirmatory. Promotion means a *new* hypothesis, a *new* trial id,
   on untouched data. The exploratory ancestor is recorded as the lead.
4. **Maturity ceilings by protocol.** EXPLORATORY caps at L1.
   CONFIRMATORY reaches L3–L4. L5 requires independent replication; L6
   requires stress; L7 requires the strategy path.

Existing project rules that generalize unchanged: near-misses stay
closed; reopening requires a new spec, a stated reason, and a raised bar.

---

## 6. Migration of the existing 120 trials

Retroactive **labelling only. No verdict changes, no re-grading, no
recomputation of any historical result.**

- Each of the 120 ledger entries is assigned `family`, `grade`,
  `protocol`, and `selection_set_id`, derived strictly from what its
  committed doc says.
- Where a doc is ambiguous, the trial is labelled `AMBIGUOUS` and
  counted conservatively — i.e. into *every* burden it could belong to.
- Historical DSR figures (rotation 0.990, H42b 0.992, 43a 1.000, …) are
  preserved verbatim as `DSR_global` at their stated trial counts. Where
  the selection set can be reconstructed from the docs, `DSR_selection`
  is computed and recorded **as a new column**, clearly marked
  retrospective. It confers nothing: no spec is promoted by migration.
- The migration output is itself a committed artifact and must be
  reviewable as a diff.

Expected outcome to verify during migration: the great majority of the
120 are INFO-grade kill tests; strategy-grade trials are a much smaller
set. The exact split is a migration deliverable, not a guess.

---

## 7. Storage, per approved C3

- **Source of truth:** git. Family and hypothesis registrations are
  YAML front-matter inside `docs/hypotheses/*.md`. High-volume sweep
  results are committed alongside as line-oriented artifacts (one row
  per cell), so 10,000 cells cost one committed file, not 10,000 docs.
  The doc *declares*; the artifact *records*; git makes both immutable.
- **Derived index:** SQLite, rebuildable. `research index rebuild` must
  reconstruct the database deterministically from the repository alone.
- **Reconciliation test:** a test asserts index ≡ docs. If they diverge,
  the docs win and the build fails. Database mutation is never
  authoritative for research history.
- Deleting the SQLite file must be a no-op for research truth.

---

## 8. Invariants (each becomes a test in Layer 2)

1. Trial ids are monotonic; no id is ever reused or deleted.
2. `|G|` is non-decreasing across every operation.
3. Every trial belongs to exactly one family and one protocol.
4. A family's `m_k` may only increase via a committed amendment; the
   amendment is itself recorded as an event.
5. Cells run ≤ cells declared, per family.
6. `Σ q_k ≤ q_global`.
7. No EXPLORATORY trial can reference reserved-window data.
8. No trial's maturity exceeds its protocol's ceiling.
9. A confirmatory run against an uncommitted/dirty registration fails.
10. Rebuilding the index from git reproduces it byte-identically.
11. Every strategy verdict carries both `DSR_selection` and `DSR_global`.
12. A finding's report renders its failed replications and stress
    failures; a report missing them is invalid.

---

## 9. What this changes vs. today — stated plainly

**Nothing is relaxed.** The draft proposed relaxing the strategy-grade
bar; that proposal was rejected (§4.2, amendment 1). The
`DSR_global` ≥ 0.95 criterion stands exactly as it has since the
120-trial ledger began.

**Tightened:** every info-level cell now costs error budget; declared
grids cost their full declared size, not the number of cells run;
exploratory results cannot reach a verdict at all without a separate
confirmatory run on reserved data; conditional/subgroup analysis is
capped at research-level observation until episode rules are
pre-registered; findings must report an evidence descriptor rather than
a trial count (§4.6).

**Unchanged:** pre-registration before results; the event-driven engine
as strategy source of truth; incremental-over-deployed bars; every trial
counted and never deleted; near-misses stay closed; negative results
written up with equal care; the four existing safeguards from the audit.

**Accepted cost:** because `|G|` continues to gate strategy grade and MI
exploration adds to `|G|`, a productive MI lab makes future strategy
validation harder. This is a deliberate trade, chosen so that a
discovery engine can never lower the standard that validated the
existing book.

---

## 10. Decisions — settled 2026-08-10

| # | Question | Decision |
|---|---|---|
| 1 | Strategy-grade bar | **Unchanged.** `DSR_global` ≥ 0.95 stands; `DSR_selection` is a diagnostic with no gating power. Threshold changes require separate pre-registration. |
| 2 | `q_global` | **0.10**, configurable, versioned with every result; a methodological parameter, never tuned against results. |
| 3 | FDR procedure | **BY by default.** BH only with a pre-declared dependence-structure justification; "fewer survivors" is not a reason. |
| 4 | `M` scope | **Annual active budget + permanent `M_lifetime`.** The reset applies only to the allocation denominator; it never erases historical volume. |
| 5 | Strategy × market-state | **Research-level observation only** until minimum episode rules are finalized and pre-registered. No automatic promotion, ever. |
| 6 | MI-derived strategy changes | A state filter is a **new strategy**; full existing validation path, no shortcut. |
| 7 | Evidence reporting | Four-part descriptor (§4.6). Volume is a burden disclosure, not a strength claim. |

Remaining open, to be settled before the first conditional analysis runs
(not blocking Layers 1–4):

- The **minimum independent-episode count** for a conditional claim to
  carry a p-value at all. Needs a number and a definition of "independent
  episode".
- Whether a family may ever be **split or merged** after declaration, and
  what evidence a split requires.

---

## 11. Status

Design **approved with amendments 1–9, 2026-08-10.** Amendments are
recorded inline at the sections they modify; the rejected proposal in
§4.2 is preserved rather than deleted.

Approved implementation scope is Layers 1–4 only. The large-scale
discovery engine is **not** approved and must not be built. No new MI
data sources are approved yet.

Layer 1 — consolidating the 6 duplicated panel builders, 11
block-bootstrap copies, and 11 forward-return definitions into canonical,
regression-tested infrastructure — **does not depend on any remaining
open question** and proceeds first.

(This paragraph appeared twice in near-identical wording, an artifact of
the amendment pass; merged 2026-08-26. No content was dropped.)
