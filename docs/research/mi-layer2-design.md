# MI Lab Layer 2 — Trial Accounting Framework: audit findings & design

Date: 2026-08-11. Status: **design + audit findings, recorded before code.**
Implements: docs/research/mi-trial-accounting-design.md (approved with
amendments 1-9).
Scope rule: **accounting and classification only.** Layer 2 recomputes
nothing.

---

## 1. Audit findings on the historical corpus

A read-only audit of the 9 DSR call sites on `main` found three
methodological discrepancies between the project's stated rule and what the
code actually did. They are recorded as **correction candidates 6-8**,
alongside the five from Layer 1. None is fixed here; each requires its own
pre-registration before any recomputation.

### Correction candidate 6 — inconsistent and frozen `n_trials` benchmarking

The standing rule says *"DSR is always benchmarked against ALL trials ever
run."* The corpus contains three different regimes:

| Regime | Scripts | `n_trials` actually used |
|---|---|---|
| Frozen point-in-time ledger snapshot | final_selection, h11_strategy_study, h12_combined_study, wide_rotation_study, h41_h42_fub1_studies, h43_combo_study | 38, 55, 57, 65, 104, 107 |
| **Parameter-grid size, not the ledger** | phase3_studies, tsmom_study | `len(grid)` = **6** |
| Dual reporting | phase3_verdict | **both 6 and 23**, side by side |

Because each count is a module constant frozen in source, re-running an old
study reproduces its original figure rather than re-deflating. That is why
the goldens pass and why the discrepancy stayed invisible. `phase3_verdict`
is the most honest of the three regimes: it prints both counts.

### Correction candidate 7 — headline results not benchmarked against the current total

Each validated spec was deflated against a different N, none of them the
current ledger total of 120:

| Spec | Published DSR | `n_trials` actually used | Ledger total today |
|---|---|---|---|
| Rotation wide (H11) | **0.990** — cited as "first absolute validation" | **65** | 120 |
| Rotation + stop (H42b) | 0.992 | 104 | 120 |
| Rot-stop + bounce (H43a) | 1.000 | 107 | 120 |
| V1 + stop (H42a) | 0.744 | 104 | 120 |

PROJECT_MEMORY cites rotation's 0.990 against the 0.95 bar without recording
that it was computed at N=65. This is the exact mechanism the accounting
design predicted: as the ledger grows, a fixed Sharpe faces a rising hurdle.

### Correction candidate 8 — Sharpe variance estimated from two observations

`expected_max_sharpe` scales with `sqrt(trial_sharpe_variance)`. Three sites
estimate that variance from **two** data points:

| Site | Variance input |
|---|---|
| h12_combined_study | `variance(trial_pp)` — the two sleeves (v1, rot) |
| h41_h42_fub1_studies | `variance([pp, other_pp])` |
| h43_combo_study | `variance([pp, other_pp])` |

The deflation benchmark those three DSRs are measured against is therefore
itself highly unstable — including H43a's DSR 1.000.

### Not a finding: conventions that ARE uniform

All nine sites feed a **per-period** (not annualised) Sharpe, and all convert
Fisher excess kurtosis to Pearson with `kurt + 3.0`. No divergence found.

---

## 2. The rule, restated prospectively

The historical rule is **not** rewritten to pretend the old code followed it.
Instead:

> **Prospective rule.** Every new trial is registered through the canonical
> global accounting mechanism, and every new strategy-grade verdict is
> deflated against the canonical global trial count at the moment it is
> computed, recorded together with that count.
>
> **Historical record.** Migrated trials retain the benchmark actually used.
> Each historical DSR is stored with its own `n_trials_used`, exactly as
> published.
>
> **Explicit caveat.** The historical corpus does **not** uniformly satisfy
> the prospective rule. Two studies deflated against a parameter grid of 6
> rather than the ledger; the remainder used frozen snapshots ranging from 38
> to 107. Any cross-era comparison of DSR values is therefore invalid without
> first equalising `n_trials`, which is a recomputation and requires its own
> pre-registration.

---

## 3. What Layer 2 builds

### 3.1 Six record types

| Record | Purpose | Statistical role |
|---|---|---|
| Global history | every trial ever, monotonic id, never deleted | audit, not inference |
| Family | declared region of hypothesis space, fixed cell count | the FDR unit |
| Exploratory | broad search | charged to the family budget; capped at L1 |
| Confirmatory | pre-registered, reserved data | the only route past L2 |
| Replication | independent re-test of an existing claim | no alpha spend; survived/attempted |
| Strategy-relevant | grade = STRATEGY | the DSR selection sets |

### 3.2 Four inferential structures

INFO claims → hierarchical FDR (BY default) with proportionally allocated
budget. STRATEGY claims → DSR, prospective rule above. REPLICATION → no
correction, asymmetric bookkeeping. STRESS → can only demote.

### 3.3 Proportional α-budget

`q_k = q_global * m_k / M_annual`, giving every family the same threshold
`q_global / M` for its first discovery. `M_annual` is the active denominator;
`M_lifetime` and `|G|` are permanent and never reset.

### 3.4 The wall

Exploratory results cannot be relabelled; promotion means a new trial id on
reserved data. Maturity ceilings are enforced per protocol.

### 3.5 Storage

**Source of truth is git.** Historical trials are migrated into
`docs/research/ledger/trials.yaml` and families into `families.yaml` — new
committed artifacts that **cite** their source document rather than editing
it, so the 25 historical hypothesis documents stay byte-identical. New
hypotheses gain YAML front-matter in their own doc.

SQLite is a **derived index only**: deletable, rebuildable deterministically
from the repository, and never authoritative.

---

## 4. Migration policy

Labelling only. Every entry records `source` (the committed doc it was
derived from) and `evidence` (the verbatim verdict text). No DSR, Sharpe,
CI, verdict or published result is recomputed or altered. Where the record
is ambiguous the trial is labelled `AMBIGUOUS` and counted conservatively.

---

## 5. Why goldens cannot protect this layer

The golden fixtures pin what the research scripts print. Layer 2 sits above
them and changes nothing they print. A mislabelled family, protocol or grade
would fail no fixture. The safety net here is instead:

1. the migration artifact is a reviewable diff, derived strictly from
   committed docs;
2. a test asserts the migrated corpus reproduces the ledger's own headline
   counts (120 registered, 119 run, 1 data-blocked);
3. a test asserts every migrated DSR equals the value published in its
   golden, with the `n_trials` that produced it;
4. the 12 invariants are executable tests.

---

## 6. Correction-candidate register (running total)

| # | Candidate | Origin |
|---|---|---|
| 1 | `vol90` includes the current bar | Layer 1 |
| 2 | `illiq30` denominator semantics | Layer 1 |
| 3 | percentile spans `w + 1` observations | Layer 1 |
| 4 | cache timestamp precision / provenance | Layer 1 |
| 5 | H05 carry window is time-dependent | Layer 1 |
| **6** | **inconsistent / frozen `n_trials` benchmarking** | **Layer 2 audit** |
| **7** | **headline DSRs not benchmarked against the current total** | **Layer 2 audit** |
| **8** | **Sharpe variance from two observations at three sites** | **Layer 2 audit** |

Separately recorded, not a correction candidate: the Monte Carlo
path-simulator duplication (5 sites), out of scope by instruction.
