# H43a Bounce-Day Census — feasibility precondition for the bounded search

Date: 2026-08-26. Status: **COMPLETE — descriptive result. 0 new ledger
trials.** Reproducible: `scripts/h43a_bounce_census.py`.

Answers the precondition set in
`docs/research/bounded-search-proposal-response.md` §4, which required this
census before any bounded search over the H43a overlay's sizing
coefficients could be registered.

Companion documents: `docs/hypotheses/43-combo-batch.md` (the book being
censused), `docs/hypotheses/22-crash-bounce-strategy.md` (the overlay),
`docs/research/owncap-sizing.md` (the 0-trial precedent),
`docs/research/mi-trial-accounting-design.md` §2 (trial semantics).

---

## 0. Verdict

**The proposal's functional form is dead.** The conditioning variable it
named — trailing volatility — has essentially **no relationship** with the
daily-loss breaches it was meant to suppress:

> `corr(trailing_vol, breach indicator) = −0.0310`

and what relationship exists points the **wrong way** for the proposal.
Shrinking the overlay on high-volatility days, the direction the proposal
assumed, removes the days that generate the returns while leaving most of
the breaches in place.

Under the §4 disposition rule — *"If the census shows breaches spread across
the trigger distribution, the proposal is declined on feasibility and closed
with that as its recorded result"* — **the bounded search over
`f(trailing_vol; k1, k2)` is DECLINED.** No trials were spent to reach this,
and none should be spent pursuing that form.

This does **not** decline every conceivable conditional overlay. See §5 for
what is and is not ruled out, and for one observation that must not be
mistaken for a green light.

---

## 1. Reproduction gate

Reproduce-first, the same discipline `scripts/dsr_recheck.py` applies. The
book is rebuilt from `scripts/h43_combo_study.py`'s construction — same
cached `rot_stop_stream`, same BTC trigger, same idle-cash definition, same
equal-weight alt basket, same 0.22% round-trip cost — and checked against
the published verdict before any figure is reported.

| Quantity | Published (H43a) | Reproduced | Result |
|---|---|---|---|
| Window | 2,880 d | 2,880 d (2018-08-17 → 2026-07-05) | **match** |
| Bounce days | 317 | 317 | **match** |
| Mean idle cash deployed | 82% | 82% | **match** |

The script refuses to print any census figure if this gate fails.

---

## 2. Breach definition, derived not assumed

From `risk_management/prop_sim._run_path`, the account busts on a day where
`equity <= prev * (1 - daily_loss_pct)`, with `equity *= 1 + r * risk_scale`.
At the bars' `RISK_SCALE` of 0.5 and the firm's 3% daily rule, a **breach
day is exactly a day whose book return satisfies `r ≤ −6%`.**

---

## 3. Where the breaches are

| Book | All 2,880 days | Bounce days | Non-bounce days |
|---|---|---|---|
| rotation-stop alone (base) | **1** | 0 | 1 |
| rotation-stop + overlay | **30** | 29 | 1 |
| **Overlay's contribution** | **+29** | +29 | 0 |

`OBSERVATION` — the base book breaches the daily rule **once in 2,880
days**. The overlay adds 29, all of them on bounce days. This is the
mechanism behind H43a's bar-2 failure (prop pass 47.5% vs 73.0%), now
counted rather than inferred.

`OBSERVATION` — exactly **one** breach is on a non-bounce day. The overlay
is flat then, so no sizing rule can touch it. One breach is the floor any
conditional rule is working down towards.

### Return distributions

| Series | n | mean | min | p05 | p50 | p95 | max |
|---|---|---|---|---|---|---|---|
| base, all days | 2,880 | +0.0011 | −0.0687 | −0.0189 | +0.0000 | +0.0233 | +0.1634 |
| combined, all days | 2,880 | +0.0019 | **−0.1683** | −0.0236 | +0.0000 | +0.0345 | +0.2468 |
| base, bounce days | 317 | +0.0020 | −0.0433 | −0.0160 | +0.0000 | +0.0208 | +0.0554 |
| combined, bounce days | 317 | +0.0091 | **−0.1683** | −0.0895 | +0.0096 | +0.0839 | +0.2468 |
| overlay alone, bounce | 317 | +0.0071 | −0.1610 | −0.0733 | +0.0076 | +0.0795 | +0.2471 |

`OBSERVATION` — the overlay roughly **quadruples** mean return on bounce
days (+0.0020 → +0.0091) and simultaneously takes the worst day from
−4.33% to −16.83%. Both halves of H43a's verdict in one row.

---

## 4. The relationship the proposal depends on — measured

The proposal scoped its search to `overlay_size = base_size *
f(trailing_vol; k1, k2)`. That form can only work if breaches concentrate
where trailing vol is high. Bounce days, split into quintiles by the
20-day trailing volatility of the base book (lagged one day, so it is
strictly knowable before the bounce):

| Quintile | trailing vol range | n | breaches | overlay P&L (sum) | overlay P&L (mean) |
|---|---|---|---|---|---|
| Q1 (lowest) | [0.0000, 0.0064] | 63 | **9** | **−0.1518** | −0.00241 |
| Q2 | [0.0065, 0.0103] | 63 | 5 | +0.2321 | +0.00368 |
| Q3 | [0.0103, 0.0128] | 63 | 6 | +0.5925 | +0.00940 |
| Q4 | [0.0129, 0.0170] | 63 | 3 | +0.5283 | +0.00839 |
| Q5 (highest) | [0.0170, 0.0388] | 64 | 6 | **+1.0017** | +0.01565 |

`OBSERVATION` — breaches are **9, 5, 6, 3, 6** across the vol range. There
is no tail to cut. The *lowest*-volatility quintile carries the *most*
breaches.

`OBSERVATION` — correlations over the 316 bounce days with a defined
trailing vol:

- `corr(trailing_vol, breach indicator)` = **−0.0310** — no relationship.
- `corr(trailing_vol, overlay P&L)` = **+0.1113** — the high-vol days are
  the *profitable* ones.

`INTERPRETATION` — these two together are why the proposal's form cannot
work. It would shrink exposure exactly where the overlay earns
(corr +0.11) in order to suppress breaches that are not there (corr −0.03).
The trade it assumed exists runs backwards.

### The descriptive trade-off curve

"Zero the overlay on the top X% of bounce days by trailing vol" — the
proposal's direction. Published whole; **no row is selected.**

| X% | breaches left | overlay P&L kept | % of P&L kept |
|---|---|---|---|
| 0 | 29 | 2.2028 | 100.0% |
| 5 | 27 | 2.0431 | 92.8% |
| 10 | 25 | 1.9647 | 89.2% |
| 20 | 23 | 1.2040 | 54.7% |
| 30 | 22 | 0.7417 | 33.7% |
| 40 | 20 | 0.6461 | 29.3% |
| 50 | 16 | 0.4222 | 19.2% |
| 75 | 12 | −0.2092 | −9.5% |
| 100 | 0 | 0.0000 | 0.0% |

`OBSERVATION` — cutting the top 20% of vol days removes **6 of 29**
breaches and **45% of the overlay's P&L**. Reaching zero breaches requires
removing 100% of the overlay, which is rotation-stop alone — the outcome
that fails bar 1 by construction, exactly the squeeze §4 of the response
predicted.

---

## 5. What is NOT ruled out — and one flagged observation

**Ruled out:** the specific pre-scoped form `f(trailing_vol; k1, k2)` in
the direction proposed. A bounded search over it would spend ~196 trials to
land somewhere on the table above, all of which is already visible for free.

**Not ruled out:** a conditional overlay on some *other* conditioning
variable. This census measured one variable because the proposal named one.

### Flagged post-hoc observation — NOT a candidate

The census was run symmetrically, because a census that only looks in the
direction the proposal assumed would be a biased census. The other arm —
"zero the overlay on the **bottom** X% by vol" — reads:

| X% | breaches left | overlay P&L kept | % of P&L kept |
|---|---|---|---|
| 0 | 29 | 2.2028 | 100.0% |
| 10 | 24 | 2.3661 | 107.4% |
| 20 | 20 | 2.3546 | 106.9% |
| 30 | **16** | **2.4574** | **111.6%** |
| 50 | 13 | 1.7805 | 80.8% |
| 75 | 6 | 1.3339 | 60.6% |

`OBSERVATION` — the low-volatility bounce days appear to be pure cost:
they lose money **and** carry the most breaches.

**This is recorded as an observation and explicitly NOT advanced as a
hypothesis.** It was found by looking at the data after the fact, which is
the precise activity this project's rules exist to prevent from becoming a
claim. Three things would have to be true before it could be tested, and
none of them are true today:

1. It needs a **market hypothesis stated first** — a reason low-vol
   post-crash days should behave differently, written before any bar is
   evaluated. Without one this is a shape in 316 observations.
2. It needs its own **pre-registered document and bars**, per the standing
   rule. It cannot inherit H43a's.
3. It must clear `DSR_global` at the post-search N like anything else.

Quoting the table above as evidence for that rule would be circular: the
rule was derived from this table. The table can motivate a hypothesis; it
can never confirm one.

---

## 6. Trial accounting

**0 new ledger trials.** The ledger stands at 125, unchanged.

Justification, following `owncap-sizing.md`'s precedent (which swept five
leverage values over this same book and declared 0 trials): this study
**describes** distributions and publishes both trade-off curves whole. It
selects no operating point and advances no candidate. Under the
description-versus-selection rule proposed as amendment 10 in
`mi-trial-accounting-design.md` §2, description does not consume alpha.

Note that the verdict in §0 does not depend on that amendment being
ratified. It is a **decline**, and declining costs nothing under any reading
of the rule: no candidate was promoted, and the strict unqualified rule's
concern — a winner chosen from cells that were compared — has no subject
here because there is no winner.

**The line, stated so it is not crossed later:** choosing a row from either
table because it scored best is a selection over the rows it beat, and costs
that many trials. This document reports and stops.
