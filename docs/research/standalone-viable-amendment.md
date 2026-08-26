# Methodological Amendment — separating existence from deployment

Date: 2026-08-27. Status: **DECIDED — owner, 2026-08-27. In force.**
Amends: `CLAUDE.md` standing rule *"New features must beat the DEPLOYED
system incrementally, not zero."*
Prompted by: `docs/research/graveyard-audit.md` §2.

This is a change to what a verdict **means**, not to any threshold. No
existing verdict is reversed by this document, and none may be relabelled
under it without being re-checked against §3.

---

## 1. The defect

The standing rule answers two different questions with one answer:

1. **Existence** — does this edge exist at all?
2. **Deployment** — should this go into the current book?

The rule is correct for (2) and is being applied to (1). A hypothesis that
makes money standalone, but less than the incumbent adds, is recorded as
`KILLED` — the same terminal status as a hypothesis with no edge at all.

`OBSERVATION` — the ledger therefore cannot distinguish between
`docs/hypotheses/04-mean-reversion.md` ("REJECTED — decisively", no edge)
and `docs/hypotheses/23-incremental-features.md` (killed as redundant,
whose input signal H13 measured a CI of **[+1.25%, +5.99%]**).

`INTERPRETATION` — this is a loss of information, and it compounds. If the
deployed book is ever changed or retired, every edge that was killed *for
being redundant to it* is sitting in the graveyard indistinguishable from
the edges that were never real. The rule that protects the book from
redundancy is also erasing the bench.

---

## 2. What is NOT changing

Stated first, because the rule being amended has already earned its keep
and the amendment must not be read as weakening it.

- **Deployment still requires beating the incumbent.** Nothing enters a
  paper account, the combined book, or any live path on standalone merit.
  The incremental bar is untouched for that decision.
- **Meta-finding 4 stands.** "Info-signal ≠ strategy improvement" was
  learned the hard way (7d ranking real at info level, degraded the
  walk-forward; shock signal real, fully absorbed by deployed momentum).
  Both remain correctly not-deployed.
- **No threshold moves.** `DSR_global ≥ 0.95` is unchanged, per
  `mi-trial-accounting-design.md` §4.2.
- **No trial count changes.** These trials are already counted. This
  relabels an outcome; it re-runs nothing and spends nothing.

---

## 3. The amendment

A third terminal outcome is added alongside `PASS` and `KILLED`:

> **`STANDALONE-VIABLE`** — this hypothesis cleared a full standalone bar
> on its own merits, and did **not** beat the deployed system. It is not
> deployed. It is recorded as a live edge on the bench, re-examinable
> whenever the deployed book changes.

**The standalone bar is a real bar.** To be recorded `STANDALONE-VIABLE`, a
hypothesis must meet **every** requirement a deployment claim meets, except
the comparison to the incumbent:

1. Positive expectancy **after the full cost model** — fees, half-spread,
   participation impact. No gross-of-cost result qualifies.
2. A 95% confidence interval **excluding zero**, by the same block-bootstrap
   estimator its family already uses.
3. **`DSR_global ≥ 0.95`** against the global trial count, exactly as a
   strategy-grade claim.
4. Engine-grade: produced by the event-driven engine, not a vectorized
   screen.
5. A pre-registered hypothesis document, as always.

Anything failing any of these is `KILLED`, as before. There is no partial
credit and no "point estimate was positive" route in.

---

## 4. The risk, and the guard

`INTERPRETATION` — the honest danger is that a softer category rots into a
dumping ground for near-misses, and the ledger quietly stops recording
failure. That would destroy the only asset this project has.

Three guards:

- **The bar in §3 is not softer.** It is the deployment bar minus exactly
  one comparison. A `STANDALONE-VIABLE` result is *more* evidenced than
  most published retail strategies, not less.
- **No retroactive relabelling from the armchair.** Existing `KILLED`
  verdicts stay `KILLED` until re-registered and re-run against §3. The
  graveyard audit's candidates (FU-B1, H02) are *recommendations to
  re-register*, not reclassifications.
- **`STANDALONE-VIABLE` is not a promotion path.** It cannot become
  eligible for paper or live deployment by accumulating time or being
  looked at again. It re-enters only through a fresh pre-registration
  against whatever the incumbent is on that day.

---

## 5. What this changes in practice

`OBSERVATION` — the ledger's headline currently reads as ~4 survivors from
125 trials. Under this amendment the same history would read as three
groups rather than two: no-edge, real-but-redundant, and deployed.

`INTERPRETATION` — that is a materially different research finding, and the
second group has never been counted. How large it is, is unknown until the
candidates are actually re-run; the graveyard audit identified four
suspects and proved none of them. The honest claim today is that the
partition exists, not that it is large.

---

## 6. Consequence for the near-miss rule

The "near-miss rule" (close a hypothesis that misses its bars, record the
figures) is unchanged in mechanics. Its scope narrows: a hypothesis that
misses **only** the incremental comparison, while clearing §3, is closed as
`STANDALONE-VIABLE` rather than `KILLED`.

A hypothesis that misses any §3 requirement is still closed as `KILLED`,
including one that misses by a hair. Near-miss remains a kill.
