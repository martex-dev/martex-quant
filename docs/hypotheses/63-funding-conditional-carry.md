# Hypothesis 63 — Funding-Conditional Carry

Status: **GATE A + GATE B PASS (2026-08-27) — strategy-grade, replaces H62
as the carry spec, paper-eligible.** Trials: **+3 → 129.** Verdict in §7.
**Read §7.2 before sizing:** it does NOT fix the dead recent regime
(+0.08%/yr → +0.15%/yr). A filter cannot create a premium nobody is paying.

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

---

## 7. VERDICT (2026-08-27, scripts/h63_conditional_carry_study.py, +3 → 129)

**GATE A AND GATE B BOTH PASS.** Primary cell L = 30. Same 2,124-day
window as H62, incumbent figures recomputed in the same run.

### The declared grid — all three cells, as promised

| L | Sharpe | CAGR | MDD | DSR | 2022 net |
|---|---|---|---|---|---|
| 7 | 5.00 | +3.73% | −2.21% | 1.0000 | −1.43%/yr |
| **30 (primary)** | **6.00** | **+4.51%** | **−0.51%** | **1.0000** | **−0.01%/yr** |
| 90 | 5.89 | +4.27% | −0.63% | 1.0000 | −0.05%/yr |
| *incumbent (always-on)* | *2.29* | *+3.24%* | *−5.09%* | — | *−4.83%/yr* |

| Gate | Bar | Measured | Result |
|---|---|---|---|
| A1 | CI excludes zero | +1.205 bp/day, CI [+0.697, +1.867] | **PASS** |
| A2 | CAGR ≥ 2%/yr | +4.51% | **PASS** |
| A3 | Sharpe ≥ 1.0 | 6.00 | **PASS** |
| A4 | DSR ≥ 0.95 @129 | 1.0000 | **PASS** |
| B5 | Sharpe > 2.29 | 6.00 | **PASS** |
| B6 | CAGR > +3.24% | +4.51% | **PASS** |
| B7 | 2022 > −4.83% | **−0.01%** | **PASS** |

### 7.1 Why this is believed rather than merely passed

`OBSERVATION` — **all three cells pass and agree** (Sharpe 5.00 / 6.00 /
5.89). A 13× lookback range producing the same answer is a **plateau, not
a spike**. This is the robustness signature H58's ablation bar was designed
to demand, obtained here without a separate perturbation test because the
grid *is* the perturbation.

`OBSERVATION` — **the filter improves every single year, monotonically**:
2020 +4.15→+6.68, 2021 +15.68→+15.95, 2022 −4.83→**−0.01**, 2023
+1.75→+2.49, 2024 +4.57→+4.89, 2025 +0.45→+0.63, 2026 −0.78→−0.63. Seven
of seven. No year is made worse.

`OBSERVATION` — **deployment is 79.2% of symbol-days.** The Sharpe is not
an idle-capital artifact: the book is held most of the time and the
volatility reduction comes from avoiding negative-carry states, not from
sitting in cash.

### 7.2 What it does NOT fix — and this is the load-bearing caveat

`OBSERVATION` — the reason H63 was written was H62's dead recent regime.
On that measure it barely moves:

| Window | Incumbent | L=30 |
|---|---|---|
| last 365 days | +0.08%/yr | **+0.15%/yr** |
| last 730 days | +0.75%/yr | +0.88%/yr |

`INTERPRETATION` — **a filter cannot create a premium that is not being
paid.** H63 removes the cost of holding through negative carry, which is
real and worth having; it does nothing about a regime where funding is
simply near zero. The current regime is the second kind. Carry, filtered or
not, earns approximately nothing today.

**Nothing in this verdict changes the income picture.** It makes an
existing small edge cleaner and much safer (MDD −5.09% → −0.51%). It does
not make it larger.

### 7.3 Meta-finding 2 now has its first documented exception

`OBSERVATION` — the pre-registration (§1) recorded the prior against this
hypothesis: *"sizing beats switching"*, with every regime filter previously
tested (H03, H06, rotation-sized) having failed. **This switch worked.**

`INTERPRETATION` — the exception has a stated mechanism, given in §2 before
the run: **the conditioning variable here is the revenue itself, not a
proxy for it.** Funding is not a prediction of the payoff — it *is* the
payoff, observable before the position is taken. Every failed regime filter
in this ledger conditioned on something correlated with returns; this one
conditions on the cash flow being collected.

**Proposed refinement to meta-finding 2, for PROJECT_MEMORY:** *switches
fail when they condition on a predictor of the payoff, and can succeed when
they condition on the payoff itself.* That is a narrower and more useful
rule than "sizing beats switching", and it was stated in advance rather
than fitted to this result.

### 7.4 Disposition

Per §5, Gate A + Gate B → **strategy-grade, candidate to replace H62 as
the carry spec, eligible for a paper account.**

Recorded with it, binding on anyone acting on this:

- **L = 30 was nominated as primary before the run.** L = 90 is within
  noise of it. Do not "select" L = 30 as though the grid chose it; the
  honest statement is that the whole grid works.
- **Do not size on +4.51%.** The forward expectation at current funding is
  ~0%/yr, exactly as for H62 (§7.2).
- **1× only.** The intraday-liquidation limitation from H62 §7 is
  inherited unchanged.
- **A limitation this data cannot see:** spot and perp closes are both
  daily UTC stamps, so measured basis drift excludes intraday divergence.
  True basis risk is understated by an unknown amount. Same family of
  caveat as the liquidation one, and it applies to H62 equally.
