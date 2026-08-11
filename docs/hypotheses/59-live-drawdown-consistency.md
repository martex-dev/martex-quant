# Hypothesis 59 — Is the live paper drawdown consistent with the backtest?

Status: **PRE-REGISTERED, NOT RUN.** Committed before the window is examined.

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
