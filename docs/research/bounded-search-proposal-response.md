# Response — Bounded Parameter Search over the H43a Overlay Sizing Rule

Date: 2026-08-26. Status: **RESPONSE — decision in principle recorded.
No trial registered, no code authorized, no hypothesis doc opened.**
Responds to: contributor proposal "Genetic-Algorithm Parameter Search,
Bounded and Pre-Declared" (2026-08-26).

Companion documents: `docs/research/mi-trial-accounting-design.md`,
`docs/research/owncap-sizing.md`, `docs/hypotheses/22-crash-bounce-strategy.md`,
`docs/hypotheses/41-combined-book.md`, `docs/hypotheses/43-combo-batch.md`,
`docs/hypotheses/58-learned-indicator-ensemble.md`, `PROJECT_STATE.md`.

Convention: `OBSERVATION` = measured fact with source. `INTERPRETATION` =
a reading, not citable as evidence.

---

## 0. Decision, up front

The proposal's three questions, answered:

1. **Acceptable in principle?** **Yes**, conditionally — as a *declared
   grid*, not a genetic algorithm (§3), and only after the feasibility
   census in §4 shows a candidate region exists.
2. **What N?** **196** (a 14×14 grid). But the reasoning behind that
   number is not the reasoning in the proposal's §3, which is
   over-weighted (§2), and it is not obviously a trial-consuming
   exercise at all until a distinction the proposal did not draw is
   settled (§5).
3. **Wait for the trial-accounting design?** **Yes.** Correctly
   anticipated, and it matches next-action #1 in `PROJECT_STATE.md`.

Two substantive items must be resolved before a hypothesis doc can be
opened: the value question in §6 and the specification question in §7.

---

## 1. Verification pass

Every external claim in the proposal was checked against the repository
at commit state 2026-08-26. This is recorded because the proposal is
from outside the project, and its citations carry weight only if they
survive checking.

| Claim | Source checked | Result |
|---|---|---|
| §4.2 proposed replacing the global-N bar with selection-set-N, was REJECTED, recorded not deleted | `mi-trial-accounting-design.md` §4.2 | **Accurate**, including the "recorded rather than deleted" rationale |
| "a computed-but-unread cell inside an automated sweep IS a trial" | ibid. line 77 | **Accurate, verbatim** |
| N=120 → 2.594; N=10,000 → 3.861 (×1.49) | ibid. lines 62–63 | **Accurate** |
| H43a: Sharpe 1.55 vs 1.47, CAGR +79.0% vs +42.9%, DSR 1.000, prop pass 47.5% vs 73.0%, MDD −37.6% vs −29.0% | `43-combo-batch.md` | **Accurate on every figure** |
| H41: Sharpe 1.36, CAGR +66.2%, trips the 3% daily rule | `41-combined-book.md` | **Accurate** |
| `metrics.py`, `prop_sim.py`, `splits.py`, `dsr_recheck.py` exist at the given paths | filesystem | **All present** |
| Large-scale discovery engine NOT approved | `PROJECT_STATE.md` | **Accurate** — and raised by the proposal against itself |
| `tesla-cnn-study.md` reported all seeds, not the flattering one | `tesla-cnn-study.md` | **Accurate** |
| `M_annual` budget mechanism | `mi-trial-accounting-design.md` line 191 | **Accurate** |

`OBSERVATION` — zero fabricated citations, zero misquoted figures.

Two structural things the proposal got right without being told:

- It located the standing H58 constraint and wrote itself to clear it
  (§4.3), rather than arguing around it.
- It surfaced the MI Lab discovery-engine precedent **against its own
  case** (§3) and named the precedent risk in §5.2. That is the correct
  behaviour for a proposal touching a deferred capability.

The RL framing from the earlier discussion was withdrawn by the proposer
with a stated reason (no MDP, no reward shaping, no new evaluation
path). That withdrawal is why this document exists; the RL version would
have been declined without a written response.

---

## 2. §3 is over-weighted — the trial cost was computed, not estimated

The proposal correctly declined to estimate the hurdle by hand and asked
for `scripts/dsr_recheck.py` to be run at hypothetical N before any
commitment. That was done.

**Method.** `dsr_recheck.py`'s own reconstructions were reused unchanged
and its reproduce-first guard was obeyed: both books reproduce their
published DSR at their original N before any recomputed figure is
reported (rotation-stop 0.9921 vs published 0.992 @104; rotation 0.9905
vs published 0.990 @65). Only `n_trials` varies. No return stream, no
estimator, and no published value was altered. **This is arithmetic on
already-validated streams and registers no trial** — the same category
as `owncap-sizing.md` and the phase-4 prop sims.

| Ledger N | rotation-stop (DEPLOYED) | rotation | E[max Sharpe], rot-stop |
|---|---|---|---|
| 125 (today) | **0.9909** CLEARS | 0.9881 CLEARS | 0.0353 |
| 225 (+200, the ask) | **0.9865** CLEARS | 0.9857 CLEARS | 0.0380 |
| 325 | 0.9831 CLEARS | 0.9841 CLEARS | 0.0395 |
| 625 | 0.9755 CLEARS | 0.9811 CLEARS | 0.0422 |
| 1,000 | 0.9688 CLEARS | 0.9787 CLEARS | 0.0441 |
| 10,000 | 0.9188 **FAILS** | 0.9649 CLEARS | 0.0523 |

**Bisection on the deployed book: clears at N=2,821, fails at N=2,822.**

`OBSERVATION` — **headroom is 2,696 further trials** before the deployed
spec loses its own bar. The proposal's 200-evaluation ask costs
rotation-stop **−0.0044**.

`INTERPRETATION` — §3 is the most carefully argued section of the
proposal and the least decision-relevant. It re-derives, defensively, a
conclusion `PROJECT_MEMORY.md` already recorded as a corrected error:

> Growing the ledger 104 → 125 cost rotation-stop only −0.0011 [...]
> **the DSR bar is far less sensitive to ledger growth than feared** —
> the earlier worry that new trials would retroactively disqualify the
> deployed book was wrong, and worth recording as wrong.

The reason the hurdle barely moves is in that entry: `expected_max_sharpe`
scales as √(2 ln N) against a trial-Sharpe variance of 0.000183, so the
benchmark moves 0.0353 → 0.0380 across the entire proposed search.

**Consequence for the proposal:** the trial budget is not the binding
constraint and should stop being treated as the central objection. The
binding constraints are feasibility (§4) and value (§6). This is not a
licence — §4.2's "as |G| grows, the strategy-grade bar gets harder [...]
accepted deliberately" stands unchanged — but it means the search should
be judged on whether it can succeed, not on what it costs.

---

## 3. Instrument — replace the GA with a declared grid

This is the one technical correction to the proposal, and it is
unambiguous.

The proposal scopes the search to coefficients of one pre-specified
functional form: `overlay_size = base_size * f(trailing_vol; k1, k2)`.
That is **two free floats**, searched with a budget of ~200 evaluations
(population 20 × generations 10).

A full grid at that budget is **14 × 14 = 196**. It is strictly better on
every axis the proposal itself argues for:

- **Determinism.** No seed, no lineage ambiguity, byte-reproducible.
  The project's golden-fingerprint regime and its reproduce-first
  discipline both assume deterministic research artifacts; a stochastic
  optimizer is a poor fit for a codebase where a CRLF change is treated
  as a reproducibility event.
- **Complete coverage.** A GA concentrates evaluations near incumbents
  by construction and can miss a region entirely. A declared grid cannot
  — its coverage is stated in advance and provable.
- **The proposal's own §4.4 becomes free.** §4.4 asks for a perturbation
  test on the winner to distinguish a narrow fitness spike from a broad
  plateau. With a grid, *the entire fitness surface is the output.*
  Plateau-versus-spike is read off it directly, at zero additional
  evaluations, and the surface itself is the publishable artifact. With
  a GA it requires extra runs and still only samples locally.
- **It defuses §5.2 almost entirely.** The proposal's own precedent
  worry is that approving a bounded search makes the next "just a small
  search" easier to approve, ratcheting toward the deferred discovery
  engine. A declared grid has no capacity to become a standing engine:
  its extent is its declaration. A GA is a general-purpose optimizer
  that happens to be pointed at two parameters this time.
- **Auditability**, which §2 argues for on interpretability grounds, is
  total rather than per-individual.

GA earns its keep in high-dimensional, combinatorial, or
non-differentiable spaces. At two floats it contributes stochasticity
and nothing else.

**Requested change:** retitle and rescope to *bounded grid search*. The
argument in §2 for why *some* search is legitimate here — reuses the
existing objective, no reward shaping, no new evaluation path, inherits
the engine's leakage guarantees — survives the swap unchanged and is
accepted.

---

## 4. Feasibility — the three-bar squeeze, and a precondition

The proposal's §5.1 names the risk that the problem is structural rather
than a sizing artifact. That risk is understated. State the target
precisely from H43a's verdict — the winner must clear **all three** bars
simultaneously:

| Bar | H43a fixed rule | Required |
|---|---|---|
| 1. Sharpe vs rotation-stop alone | 1.55 vs 1.47 — **PASS** | must stay **> 1.47** |
| 2. Prop pass @0.5× | 47.5% vs 73.0% — **FAIL** | must exceed **73.0%** |
| 3. MDD vs 5-point rule | −37.6% vs −29.0%, 8.6 pts worse — **FAIL** | within **5 pts of −29.0%** |

**The squeeze.** A conditional rule that shrinks overlay size on
high-variance trigger days converges, in the limit, on *no overlay* —
which is rotation-stop alone, which fails bar 1 by construction (Sharpe
exactly 1.47, not above it). Meanwhile the overlay's entire return
contribution (+79.0% vs +42.9% CAGR) is generated on the trigger days,
and the prop-pass damage is generated on the same days. Bar 1 and bar 2
are therefore in direct tension through a shared cause, and the search
is threading between two failure modes that are not independent.

`INTERPRETATION` (flagged) — a feasible region exists only if the
daily-loss breaches are concentrated in a thin sub-population of trigger
days rather than spread across the trigger distribution. That is an
empirical question about a run that **has already been computed**, and
it should be answered before 196 evaluations are spent discovering it.

**Precondition, required before any search is registered:**

> A descriptive census of the existing H43a run: the distribution of
> daily account P&L across its **317 bounce days** (2,880-day window,
> mean 82% idle cash deployed), and the count and vol-conditioning of
> the days that individually breach the firm's 3% daily limit.

Two notes on that census:

- **Sample adequacy is not the concern.** 317 trigger days over 2,880
  (11.0% of the calendar) is a real sample; a two-coefficient rule fit
  on a train fold of roughly 220 events with ~95 held out is defensible.
  The concern is region existence, not power.
- **It costs zero trials, by precedent.** `owncap-sizing.md` opens:
  "Descriptive sizing-policy analysis on VALIDATED streams — 0 new
  ledger trials (same category as the phase-4 prop sims)." A census of
  an already-validated stream that selects nothing falls in that
  category. This resolves the ambiguity in CLAUDE.md's "count every
  trial (including variants and descriptive horizons)" for this case;
  the operative distinction is developed in §5.

If the census shows breaches spread across the trigger distribution,
**the proposal is declined on feasibility** and closed with that as its
recorded result.

---

## 5. A distinction the proposal did not draw, and it matters

The proposal accepts, without argument, that every evaluated candidate
is a trial. That is the correct default and the correct posture. But it
imports the rule without noticing that the repository contains a
precedent pointing the other way, and the precedent needs distinguishing
rather than ignoring.

`OBSERVATION` — `owncap-sizing.md` swept **five leverage values** (1.0×,
1.5×, 2.0×, 3.0×, 4.0×) over the 43a book, reported a full metric table
per value, and declared **0 new ledger trials**.

That is, structurally, a sizing-coefficient sweep over the same book
this proposal targets. If that precedent applied here, §3 would collapse
entirely and the grid would cost nothing.

**It does not apply, and the reason is the rule worth writing down:**

> `owncap-sizing.md` **described** a curve. It selected no operating
> point on statistical grounds and made no eligibility claim; the
> leverage decision is a policy choice made by a human against a
> published trade-off table. The proposed grid **selects** — it picks
> the coefficient vector that maximises a fitness metric and advances it
> as a candidate for eligibility.
>
> **Selection against a metric is what consumes alpha. Description does
> not.** A sweep that publishes its whole surface and selects nothing
> costs no trials; the moment a winner is chosen on the metric and
> carried forward as a claim, every cell that lost the comparison
> entered the selection set.

This is consistent with `mi-trial-accounting-design.md` §2's definition
of a selection set — *"candidates whose test statistics were compared
against each other to pick a winner"* — and it explains the
computed-but-unread rule rather than merely obeying it.

**Consequence:** 196 cells, all of them trials, ledger 125 → 321,
deployed book to ≈0.983 (interpolated from §2's table; to be recomputed
exactly at registration). Recorded win or lose, per the
failure-is-a-result norm the proposal correctly cites.

`INTERPRETATION` — this distinction is proposed for adoption into
`mi-trial-accounting-design.md` when that document leaves DESIGN status.
It is offered here because the proposal's arrival surfaced it, not
because this response needs it to reach its decision.

---

## 6. The unaddressed question — value, not feasibility

The proposal frames H43a as a strategy that "fails deployment." Its
verdict says something more specific, which the proposal did not quote:

> **Disposition:** rotation-stop + bounce **replaces H41's book as THE
> own-capital archive candidate** (higher Sharpe, higher CAGR, smaller
> MDD than H41's version). Own-capital bars (not eval-shaped) to be
> registered post-funded, per the backlog.

H43a is not an open failure. It is a *routed* result — sent to the venue
where the constraint that killed it does not exist. `owncap-sizing.md`
has already sized it there: **2× leverage → +122% CAGR, −69% MDD, mean
30-day +10.0%**, with the Kelly cliff between 2× and 3× and 4× recorded
as ruin on the historical path.

Meta-finding 8 states the general principle: *"Eval-fit and
own-capital-fit are different objectives; H41's book is archived for the
own-capital stage."* The proposal is, in effect, asking to bend an
own-capital book into eval geometry after the project decided to stop
bending and change venue instead.

**That is not a refusal — it is the question that must be answered.**
There is a real value case and the proposal did not make it. The
canonical eval config is rotation-stop alone at RISK_SCALE 0.85, one
fee, no retries: **P(pass) 62.3%, bust 37.7%, median 48 days**. An
eval-eligible 43a would put a Sharpe-1.55 / +79%-CAGR book behind the
firm's capital instead of a Sharpe-1.47 / +42.9% one — and
`owncap-sizing.md`'s income ladder is explicit that *"the firm's capital
is the cheap leverage."*

**Requested before registration:** a stated EV delta — expected funded
income under an eval-eligible 43a versus the canonical rotation-stop
config, computed from the existing `prop_sim.py` machinery on the
existing streams. That is descriptive, costs zero trials by the §5 rule,
and converts "this problem is interesting" into a number.

`INTERPRETATION` — one counter-consideration, stated so the proposer can
argue against it: `owncap-sizing.md` §3 records that *"the route to
higher sustainable monthly returns is a higher-Sharpe book, not more
leverage [...] Every genuinely independent edge added raises the ceiling
itself. **This is now a primary research objective.**"* A sizing search
on an existing book does not add an independent edge. If contributor
effort is the scarce resource rather than trials, the stated primary
objective points elsewhere. The EV delta is what decides whether this is
the exception.

---

## 7. A specification point the proposal missed

`OBSERVATION` — `22-crash-bounce-strategy.md` specifies the overlay
under the heading **"Specification (ZERO tunable parameters)"**, and
notes that its −3% threshold was *"fixed in H19's pre-registration, not
re-tuned."* Its eligibility rests partly on that property.

The proposal introduces two fitted coefficients into the sizing of
exactly that component. This is defensible — the tuning is at the
book/sizing layer, not in the signal, and the signal's threshold stays
frozen — but it is a change in kind that the hypothesis doc must state
explicitly rather than inherit silently. The zero-parameter fixed rule
already serves as the mandatory no-search baseline under §4.3, which is
the right control; it must additionally be named as *the incumbent whose
zero-parameter status is being spent.*

Related: `PROJECT_STATE.md` records that crash-bounce has taken **zero
positions across 27 paper marks** — its trigger has not fired since
2026-07-12. The paper record therefore provides no independent evidence
about this overlay in either direction, and must not be cited as if it
did.

---

## 8. Sequencing and data

- **Design gate first.** `mi-trial-accounting-design.md` is still
  DESIGN — for review, and is next-action #1. Agreed with §5.3: this
  waits. The §5 distinction above is proposed as input to that review.
- **Lake refresh.** `data/lake` coverage ends **2026-07-10 21:00 UTC**
  (next-action #5). Any run touching current data is stale until
  refreshed. H43a's 2,880-day historical window is unaffected.
- **Order of operations, if it proceeds:** census (§4) → EV delta (§6) →
  design gate closes → hypothesis doc with functional form, bounds, grid
  extent, and verdict bars committed → `dsr_recheck.py` at declared N →
  run → re-run `dsr_recheck.py` to confirm declared N matches evaluated
  N.

---

## 9. What a registrable version must contain

Accepting §4.1–§4.6 of the proposal as written, with these changes:

1. **Grid, not GA.** Extent declared as an explicit cell count (§3).
2. **Census result attached** (§4), with the feasibility argument made
   from it rather than asserted.
3. **EV delta attached** (§6), or an explicit statement that the search
   is being run for information with no deployment path.
4. **Zero-parameter incumbent named** as such (§7).
5. **Full surface published**, not the winner — the grid's entire
   fitness table, which subsumes §3's "every generation logged"
   commitment and §4.4's robustness check in one artifact.
6. **Verdict bars unchanged from §4.6** — all three of (a) beat the
   fixed rule on the held-out fold, (b) clear the prop bar that killed
   H41/H43a, (c) `DSR_global` ≥ 0.95 at post-search N. Two of three is
   not a pass. This is accepted as written and is not negotiable
   downward after results exist.

---

## 10. Standing-policy note

§5.2's suggestion — that this class of request wants a standing budget
rather than ad-hoc approval, analogous to `M_annual` — is correct and is
the most useful forward-looking item in the proposal. `M_annual` and
`M_lifetime` already exist as declared/permanent counters in
`mi-trial-accounting-design.md` (amendment 2). Extending them to cover
contributor-proposed searches is a natural fit and should be raised at
the design gate rather than settled here.

`OBSERVATION` — with 2,696 trials of headroom on the deployed book (§2),
a search budget is affordable. `INTERPRETATION` — affordability is the
weakest possible reason to spend it, and the ledger's value has never
come from what it could afford.
