# Hypothesis 59 — Is the live paper drawdown consistent with the backtest?

Status: **RUN 2026-08-11 — verdict at the bottom.** The design and bars
above were committed before the window was examined; git history is the
proof, not this line.

This document exists because of the guardrail in PROJECT_STATE: the paper
drawdown of 2026-07-12..present is exactly the kind of material that invites
post-hoc explanation, and it must be registered before it is analysed. It is
being registered now, with the drawdown's SIZE already known (it is published
in PROJECT_STATE and reproduced below) but with **no conditional, subgroup,
or market-state breakdown of it yet examined.** That distinction is the whole
point of the guardrail and it is stated here so a reader can audit it.

---

## The question

rotation-stop is the deployed spec. Its backtest reported Sharpe 1.47 and a
maximum drawdown of **−29%**. Its first out-of-sample month is **−13.08%
since start, −14.70% from peak** (2026-08-11 mark, $4,346.12 from a $5,095.19
peak on 2026-07-13).

The naive readings are both wrong:

* *"It's down, the strategy is broken"* — ignores that −14.7% is half the
  worst drawdown the backtest itself predicted. A strategy that never has a
  −15% month is not this strategy.
* *"It's within the backtest range, so all is well"* — ignores that
  "within the range" is a very weak statement, and that this is the FIRST
  out-of-sample month, arriving immediately.

The answerable question sits between them:

> **How often does a 30-day window of the backtested strategy lose as much as
> the live record has?**

If the answer is "routinely", the live record is an unremarkable draw and the
correct action is to do nothing and keep collecting marks. If the answer is
"almost never", then the live record is not plausibly a draw from the
backtest's distribution and something real diverged — costs, fills, universe
composition, regime, or an optimistic backtest.

---

## What this is NOT

**This is not a search for an edge, and it spends no ledger budget.**

The ledger corrects for selection bias in edge claims: the more strategies
you try, the more likely the best one is luck. This test cannot produce an
edge. Its only possible outputs are "the deployed system is behaving as
advertised" and "it is not". Counting it against the deflated-Sharpe hurdle
for future edge claims would be a category error — it would penalise future
research for having checked whether the current system works.

**Ledger: +0. Total stays 125.**

The exemption has a hard boundary, stated here so it cannot be stretched
later: **if any result from this test is used to justify a CHANGE to a
deployed spec, that change is a new strategy.** It needs its own
registration, its own ledger cost, the event-driven engine, and the standing
incremental bar. Diagnosing is free; acting is not.

---

## Declared design

**Null hypothesis:** the live return stream is a draw from the strategy's own
backtested daily return distribution.

**Statistic:** compounded return over K calendar days, where K is the live
record's calendar span (start date to latest mark), NOT its mark count. The
paper record has a known gap at 2026-07-22..07-27 (recorded in PROJECT_STATE
as a permanently FAILED gate, not retroactively satisfied). Using calendar
span rather than mark count means the gap cannot silently shorten the
comparison window and flatter the result.

**Reference distribution:** every overlapping K-day window in the cached
backtest stream, plus a moving-block bootstrap using the corpus's existing
day-block machinery. Both are reported. If they disagree materially, that
disagreement is the finding and no p-value is quoted.

**One-sided p:** the fraction of backtest windows whose return is at or below
the live return. One-sided because the question is specifically about
underperformance; a live result that beat the backtest would raise a
different question and is not what is being tested.

### Declared cells

| Cell | Stream | Role |
|---|---|---|
| 1 | rotation-stop | **the deployed spec — the cell that matters** |
| 2 | rotation | the unstopped comparator, same family |
| 3 | vol-target | **control.** It is roughly flat live. If the method flags it as inconsistent, the method is broken, not the strategy |

crash-bounce is excluded: it has never taken a position, so it has no return
stream to test and including it would be theatre.

**Descriptive context, not a cell and not a trial:** BTC's return and the
equal-weight universe return over the same calendar window. A long-only
momentum book falling in a falling market is the least surprising outcome in
finance, and the write-up must not present the drawdown as anomalous without
saying what the market did. This is reported as context and carries no
verdict.

---

## Verdict bars — committed before results

Applied to cell 1, the deployed spec:

| p | Verdict | Action |
|---|---|---|
| ≥ 0.05 | **CONSISTENT** | No action. Keep paper trading, keep collecting marks. |
| 0.01 ≤ p < 0.05 | **WATCH** | No spec change. Re-run at 60 and 90 days. |
| < 0.01 | **INCONSISTENT** | Open a divergence hunt: costs, fill assumptions, universe composition, and whether the backtest window contained the regime the live period is in. |

**The control bar:** if cell 3 (vol-target) returns INCONSISTENT, the whole
run is void and no verdict is read from cells 1 or 2. A method that flags a
flat account as anomalous is measuring itself.

---

## Power — stated before the result, because it is the honest limit

**This test has almost no power, and a CONSISTENT verdict is not evidence the
strategy works.** n = 1 window. It is a single draw. "Consistent" means only
*failure to reject* — the live record is not extreme enough to be
distinguishable from ordinary variance. That is genuinely all it means.

Being explicit about the asymmetry: an INCONSISTENT verdict here would be
informative, because it takes a lot for a single draw to fall in the tail of
a distribution that already contains a −29% drawdown. A CONSISTENT verdict is
nearly uninformative and must not be reported as reassurance. It will be
reported as what it is.

---

## Pre-committed caveats

1. **The backtest distribution is not a neutral null.** It is the same
   backtest that selected this strategy, so it is optimistic by
   construction. Testing the live record against an optimistic null makes
   INCONSISTENT harder to reach, not easier — the test is conservative in
   the direction that matters, which is why it is worth running.
2. **Overlapping windows are not independent.** The percentile from
   overlapping windows is descriptive; the block bootstrap is the inferential
   version. Both are reported precisely so this cannot be quietly ignored.
3. **The live period is one regime.** Whatever the verdict, it is a statement
   about this month, not about the strategy in general.
4. **No spec changes off this result**, whatever it says. See the ledger
   boundary above.

---

## VERDICT — 2026-08-11, `scripts/h59_drawdown_consistency.py`

**Cell 1 (the deployed spec): INCONSISTENT. The divergence hunt is open.**

| Cell | Live | p (overlapping) | p (bootstrap) | Verdict |
|---|---|---|---|---|
| 1 rotation-stop (deployed) | −13.06% / 29d | 0.0060 | 0.0081 | **INCONSISTENT** |
| 2 rotation | −15.90% / 30d | 0.0032 | 0.0060 | **INCONSISTENT** |
| 3 vol-target (control) | +0.17% / 31d | 0.6387 | 0.4895 | CONSISTENT |

**The control passed**, so the run is not void: a method that flags a flat
account would be measuring itself, and this one does not. Both reference
distributions agree on every cell, so no disagreement clause is triggered
and the p-values are quotable.

Read plainly: **the deployed strategy's first out-of-sample month is worse
than roughly 99.2% of comparable windows in its own backtest.**

### What makes this stronger than it looks

The registration pre-committed the reason: the null here is the same
backtest that *selected* this strategy, so it is optimistic by construction.
An optimistic null makes INCONSISTENT **harder** to reach. Reaching it
anyway is the informative direction.

### What makes it weaker than it looks — three things, all load-bearing

1. **Cells 1 and 2 are not two confirmations.** The ledger records
   rotation-stop × rotation correlation at **0.821**. They are one event
   observed twice. Treating them as independent evidence would be exactly
   the error meta-finding 5 was written about.
2. **−13.06% is not unprecedented, only rare.** The worst 29-day window in
   the backtest is **−17.53%**, materially worse than the live month. The
   claim is about frequency, not about a magnitude the strategy never
   produced.
3. **n = 1 window.** This says the first month was a bad draw at the ~0.8%
   level. It does not establish that the strategy is broken, and nothing
   here licenses that word.

### The descriptive context could NOT be computed — an operational finding

The registration required reporting what the market did over the same
window, on the grounds that a long-only momentum book falling in a falling
market is the least surprising outcome in finance.

**That could not be done.** The research lake ends **2026-07-09**; the paper
record starts **2026-07-10**. There is *zero overlap*. Verified directly, not
inferred from a failed filter.

Two consequences, and the second matters more:

* The verdict above stands on its own terms — the comparison is live record
  versus backtest distribution, and needs no market data. But the single
  most obvious alternative explanation ("the whole market fell") is
  **currently untestable**, so it is neither supported nor excluded.
* **The research lake has not been updated in over a month.** No research in
  this repository can currently examine the live paper period at all. That
  is an operational gap, not a research result, and it blocks the first step
  of the divergence hunt this verdict just opened.

One incidental benefit: the backtest streams end 2026-07-05 and the live
record starts 2026-07-12, so the two are cleanly non-overlapping. The null
contains no part of the period being tested.

### What happens next — and what explicitly does not

The pre-registered action is a divergence hunt: costs, fills, universe
composition, and whether the backtest window contained the regime the live
period is in. Its first step is refreshing the lake, because without it the
market-context question cannot be asked.

**No spec change follows from this document.** That boundary was registered
before the test ran and is not renegotiated by the result. Any change to a
deployed spec is a new strategy: its own registration, its own ledger cost,
the event-driven engine, and the standing incremental bar.

**Ledger: +0, total remains 125**, as registered.
