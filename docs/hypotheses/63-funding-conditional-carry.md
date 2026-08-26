# Hypothesis 63 — Funding-Conditional Carry

Status: **PRE-REGISTERED 2026-08-27, NOT RUN.** Trials: **+3 → 129.**

Follows `docs/hypotheses/62-delta-neutral-carry.md` (ALL FIVE BARS PASS,
Sharpe 2.29, corr with rotation-stop +0.0041 — but the edge is concentrated
in 2021 and earns **+0.08%/yr at Sharpe 0.34 over the last 365 days**).

**Committed before any code for it exists.** No result exists at the time
of writing.

---

## 1. The problem this targets

H62 is always-on. It therefore collects the premium when longs are crowded
**and pays it when shorts are** — 2022 cost −4.83%/yr, and the recent
regime pays approximately nothing.

The obvious question, and the reason it must be registered rather than
bolted on: **does refusing to hold when funding is thin or negative
recover enough to matter, or does the filter just chase its own tail?**

`OBSERVATION` — the project's own meta-finding 2 is *"sizing beats
switching"*: vol-target sizing survived where **every** regime filter
tested (H03, H06, rotation-sized) failed. This hypothesis is a switch. The
prior from this ledger is that it fails.

`OBSERVATION` — meta-finding 4 adds the second warning: an info-level
signal that is real can still degrade a walk-forward because *the selector
chases noise*. A funding filter is a selector.

Both are recorded here **before** the run so that a pass has to overcome a
stated prior, and a failure is not a surprise that gets explained away.

## 2. Why it might work anyway

Unlike the failed regime filters, the conditioning variable here is **the
revenue itself**, not a proxy for it. Funding is not a prediction of the
payoff — it *is* the payoff, observable before the position is held. A
filter on "was I being paid recently" is closer to not-trading-for-free
than to market timing.

## 3. Specification — one declared 3-cell grid, no tuning

Identical to H62 in every respect (same 8 symbols, same 1× collateral-
ization, same cost model on both legs, same daily rebalance, same engine)
**except** the hold rule:

> Hold symbol *i* on day *t* only if the **trailing L-day mean funding for
> symbol *i*, measured through *t−1*, is positive.** Otherwise hold no
> position in *i* that day. Capital not deployed sits in cash earning zero.

`L` is declared now as a **3-cell grid: L ∈ {7, 30, 90}**. Nothing else
varies. The grid is fixed before the run and **all three cells are reported
regardless of outcome**, win or lose. Per
`docs/research/mi-trial-accounting-design.md` §2, every evaluated cell is a
trial: **this hypothesis costs 3 trials, not 1.**

L = 30 is nominated **now** as the primary cell, because 30 days is the
block length this project uses everywhere else. If a different L wins, that
is reported as a grid result — not promoted to "the spec" without its own
re-registration.

## 4. Pre-registered bars

**Gate A — is it a real edge at all?** (the `STANDALONE-VIABLE` bar)

1. Mean daily net > 0, 95% block-bootstrap CI (30-day blocks) excluding zero.
2. Net CAGR ≥ 2%/yr after all costs.
3. Sharpe ≥ 1.0.
4. `DSR_global` ≥ 0.95 at N = 129.

**Gate B — does it beat the incumbent it is meant to replace?**

5. **Sharpe > 2.29** (H62 always-on, same window).
6. **Net CAGR > +3.24%** (H62 always-on, same window).
7. **2022 net > −4.83%** — the specific regime this filter exists to
   survive, named in advance so the test is not graded on a window chosen
   after the fact.

Bars 5–7 are measured on the **identical common window** as H62, computed
in the same run. The FU-B1 defect recorded in
`docs/research/graveyard-audit.md` §2.1 — an absolute bar imported from a
different window than the incumbent's own figure — must not recur here.

## 5. Disposition, declared in advance

- **Gate A and Gate B both pass** → strategy-grade, candidate to replace
  H62 as the carry spec, eligible for a paper account.
- **Gate A passes, Gate B fails** → **STANDALONE-VIABLE** per
  `docs/research/standalone-viable-amendment.md`. A real edge that does not
  beat always-on carry. Not deployed. H62 remains the carry spec.
- **Gate A fails** → **KILLED**, and it becomes the **third** independent
  confirmation of meta-finding 2 ("sizing beats switching"), which would be
  a genuinely valuable negative result.

## 6. What this hypothesis is NOT

- It is **not** a funding *forecast*. It conditions on realized trailing
  funding only.
- It does **not** introduce leverage. 1× collateralization is inherited
  from H62 and the §7 intraday-liquidation limitation is inherited with it.
- It does **not** get to select its own window. All figures are computed on
  H62's common window in the same run.
