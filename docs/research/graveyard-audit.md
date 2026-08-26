# Graveyard Audit — what actually killed the 121

Date: 2026-08-27. Status: **COMPLETE — descriptive. 0 new ledger trials.**

Commissioned to test a specific challenge from the owner: *"From 125 only
one profitable — that's impossible. Either the tests are false or we tested
bad strategies."*

This audit classifies every killed hypothesis by **why** it died, and asks
one question of each: was this "no edge found", or "an edge found and then
rejected for a reason other than its absence"? The second category is the
one that matters, because a portfolio-construction answer used as an
existence test hides real edges.

No verdict is reversed here. Reversing one requires its own
pre-registration. This document only says what the ledger already contains,
read back honestly.

---

## 0. Headline

**The challenge is partly right.** The tests are not false — but a
meaningful minority of kills were **not** "no edge". Four hypotheses
produced measurable signal and were rejected by an incremental or absolute
bar, and in at least one case **the bar was one the incumbent also fails.**

Corrected count: it is not "1 of 125 worked". It is closer to:

| Outcome | Count (hypothesis-level) |
|---|---|
| No measurable edge — correctly killed | the large majority |
| **Real signal, killed by a bar rather than by absence of edge** | **4 cases (§2)** |
| Real signal, genuinely below trading costs | 4 intraday confirmations (§3) |
| Real edge, passed its bar, **never built** | 1 — H05 carry (§4) |
| Validated, deployed | 4 paper specs + H43a (own-capital archive) |

---

## 1. The tests are not false — one axis checked and cleared

Before crediting the challenge, the obvious suspect was checked and
eliminated.

`OBSERVATION` — the global-N deflation is **not** what is killing
hypotheses. Measured on the deployed book: it clears the 0.95 bar until
**N = 2,821 trials**, i.e. 2,696 trials of headroom from today's 125. The
benchmark `expected_max_sharpe` moves 0.0353 → 0.0380 across a 200-trial
addition. Whatever is killing hypotheses, it is not the multiple-testing
correction.

`OBSERVATION` — the cost model (`execution/simulated.py`: `fee_bps = 10.0`,
`half_spread_bps = 1.0`, plus participation impact; ~22bp round trip) is the
honest Binance retail taker rate. A BNB discount would cut it ~25%. The
intraday family died against measured edges of 2–4bp per event — a 5–10×
gap that a cost improvement does not close.

`INTERPRETATION` — "the tests are too strict" is false as a general claim
about the statistics. It is true, specifically and narrowly, about the
**incremental bar**. §2 is that case.

---

## 2. Real signal, killed by a bar — the four cases

### 2.1 FU-B1 (H33 horizon blend) — the clearest case

Verdict text, `docs/hypotheses/33-40-timeseries-batch.md`:

> **KILLED.** blend-V1 Sharpe **0.60 vs V1 0.53** (bar1 PASS, MDD also
> better: **−22.0% vs −25.1%**), but prop pass @1.5x **28.0%** vs the
> registered **>50.0%** bar — FAIL. Honest note: **V1 itself shows only
> 27.9% on this same shortened window** (the 50% figure came from the
> longer phase-5 window) [...] Blend DSR 0.857.

`OBSERVATION` — the candidate **beat the incumbent on Sharpe and on
drawdown**, and **matched it on prop pass** (28.0% vs 27.9%). It was killed
by an absolute bar of 50%, calibrated on a *different, longer window*, and
applied on a window where the incumbent scores 27.9%.

`INTERPRETATION` — this is a **bar-calibration defect**, not a verdict about
the strategy. An absolute threshold imported from one window and applied to
another is not a like-for-like comparison. The original verdict was
scrupulously honest about it — it wrote the incumbent's 27.9% down in
plain sight — but still closed the hypothesis under the near-miss rule.

**This is the strongest candidate for re-registration in the entire
graveyard.**

### 2.2 H02 — daily time-series momentum

> per-symbol median DSR rose **0.624 → 0.911** with 3× the sample
> (**BTC 0.968, BNB 0.962, DOGE 0.999**), **5/8 beat B&H over ~7y OOS** —
> "the signal strengthened with 3x the sample, which is what a real (if
> modest) edge looks like." Common-window portfolio: Sharpe 0.67, DSR
> **0.592**.

`OBSERVATION` — three symbols individually exceed the project's own 0.95
bar. The **equal-weight portfolio** is what fails, at DSR 0.592.

`INTERPRETATION` — this is an **aggregation** failure, not an edge failure.
The per-symbol evidence strengthened materially with more data, which is
the signature of real (modest) edge rather than fitting.

**Caveat, stated because it is the exact trap this project exists to
avoid:** "BTC, BNB and DOGE clear 0.95" is a selection of the best 3 of 8
after seeing the results, and must never be quoted as a validated claim.
The defensible statement is the *median* — 0.911 across all 8, up from
0.624 — plus 5/8 beating buy-and-hold. Any re-test must pre-commit to the
symbol set before running.

### 2.3 / 2.4 H23a and H23b — killed explicitly by the incremental bar

> **BOTH FAILED — features are redundant.** "The graduated features must
> beat the information the deployed systems already use, not zero."

`OBSERVATION` — both inputs were **already-measured real signals** (the
H13 shock bucket: +1.25% to +5.99% CI, a clear continuation signal; the
H08/H10 funding work). They were killed as *increments to the deployed
momentum book*, not as standalone claims.

`INTERPRETATION` — correct as portfolio decisions, and correctly recorded
as meta-finding 4 ("info-signal ≠ strategy improvement"). But they answer
"does this add to rotation-stop?", not "does this make money?". Those are
different questions and only the first was asked.

### Also in this class: the combined books

H12, H41 and **H43a** were killed by **prop-constraint geometry**, not by
absence of edge. H43a: **Sharpe 1.55, CAGR +79.0%/yr, DSR 1.000** — killed
because the overlay's variance trips a 3%-daily-loss rule. It is already
disposed of as the own-capital archive candidate, and `owncap-sizing.md`
sizes it at ~+122% CAGR at 2× leverage. **These are not failures. They are
strategies whose venue was wrong.**

---

## 3. Real but genuinely sub-cost — correctly killed

Four independent confirmations (H44 ORB, H45 first-hour, H53 aggressor
flow, H57 POC) each measured a **real** intraday reversion premium of
**2–4bp per event**, against ~22bp round-trip costs. H57: "+0.028% per
event, SIGNAL, sub-toll — closed."

`INTERPRETATION` — these kills are sound and should not be revisited at
retail cost structures. The edge is real and belongs to whoever pays
rebate-tier fees. Nothing here is recoverable by better testing.

---

## 4. Passed its bar and was never built

**H05 — carry (delta-neutral funding harvest).** Status: *FEASIBILITY
CONFIRMED*. Measured gross annualized funding premium over 4 years:
**BTC +6.86%, ETH +6.46%, XRP +5.81%, DOGE +7.90%** — 4 of 5 majors clear
the pre-registered 5%/yr bar. SOL −5.91%.

It was deferred because the engine is single-instrument spot and needs a
two-leg spot+perp portfolio with margin/liquidation modelling, "scheduled
AFTER Phase 4". Phase 4 completed. **The build never started.**

`OBSERVATION` — recorded caveat from the study itself: the *recent* funding
regime is much thinner than the 4-year mean, and the premium is
regime- and symbol-dependent. This is gross, before fees, basis bleed and
tail risk.

`INTERPRETATION` — carry is a **different risk shape** from everything else
in the ledger: low return, high Sharpe, market-neutral. It is the kind of
edge that is levered rather than traded directionally. That makes it
complementary to the momentum book rather than competing with it, and
meta-finding 3 (cross-sectional edges feed on breadth) does not apply.

---

## 5. The structural finding

`OBSERVATION` — classified by *kind*, the ledger is narrow. Almost every
tested hypothesis is **directional timing on daily bars, spot only, top-40
coins**: momentum, mean reversion, vol filters, breakouts, rotation,
calendar, intraday fades.

Untested entirely: cross-exchange arbitrage, market making / liquidity
provision, options and variance-risk premium, statistical arbitrage /
pairs. Tested-and-shelved: carry (§4).

`INTERPRETATION` — the 3% survival rate is **not** evidence that markets
are random. It is evidence about **one family** — the most competed-away
one, and the only one reachable with a retail spot account and daily bars.
The families where professional crypto money is actually made are largely
absent from the ledger, and their absence is an infrastructure gap, not a
research result.

---

## 6. Recommendations (each requires its own pre-registration)

1. **Re-register FU-B1** with a like-for-like bar. The original comparison
   used an absolute threshold from a different window; the honest bar is
   *"beat the incumbent measured on the same window"*, which it did on
   Sharpe and MDD and matched on prop pass.
2. **Re-register H02** as a pre-committed per-symbol specification rather
   than an equal-weight portfolio — with the symbol set fixed *before*
   running, and the §2.2 caveat respected.
3. **Build carry (H05).** Highest expected value in the repository: an
   edge that already cleared its own pre-registered bar and has never been
   implemented.
4. **Amend the standing rule.** "Beat the deployed system, not zero" should
   apply to *deployment* decisions, not to *existence* tests. A hypothesis
   that beats zero but not the incumbent is a real edge in the wrong
   portfolio slot, and should be recorded as such rather than as a kill.
   This is a methodological change and needs its own decision.

`OBSERVATION` — none of the above is a claim that any of these strategies
is profitable. Each is a claim that the recorded reason for its death does
not support the conclusion "no edge here."
