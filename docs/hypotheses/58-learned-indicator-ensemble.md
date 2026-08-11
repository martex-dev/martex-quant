# Hypothesis 58 — Learnable Weighted Indicator Ensemble

Status: **PRE-REGISTERED, NOT RUN.** Committed before any result exists.
Ledger: **+5 trials -> 125** (info grade). Strategy grade is a SEPARATE
registration, not granted by this document.

---

## The claim

Individual indicators may each carry weak or noisy predictive information,
but a model can learn how much each should contribute, and the weighted
combination may carry information the parts do not.

Formally, at time *t* with indicators `X(t)`:

```
S(t) = X(t) · W + b        P(entry | X_t) = sigmoid(S(t))
```

with `W` learned from data available strictly before *t*.

---

## What the existing ledger already says about this shape of idea

This is not a new question for the project, and the pre-registration has to
say so.

**H33 — multi-horizon blend — is the same shape and it died at strategy
grade.** It combined three momentum horizons into a composite score. At the
information level the score was monotone and significant (+2.41%, CI above
zero). The strategy-grade follow-up, blend-V1, was **KILLED**: Sharpe 0.60
against the deployed 0.53, but prop-firm pass rate 28% against a 50% bar.

**H12 — the 50/50 combined book — also died.** True sleeve correlation 0.77:
"blend averages, doesn't insure."

**Meta-finding 4 governs this hypothesis: info-signal ≠ strategy
improvement.** A composite that is significant at the info level has already,
once, failed to become a better strategy.

So the honest prior is unfavourable. That is a reason to test carefully with
a high bar, not a reason to skip the test — logistic regression across
*different indicator families* is a genuinely different object from blending
three momentum lookbacks, and the question of learned versus equal weights
was never asked.

## One design change forced by the evidence

**H36 killed the short leg**: "bottom-2 does NOT keep falling; long/flat
stands." Formulations that predict SHORT (the proposal's options 1, 3 and 4)
therefore contradict a settled result in this corpus.

This registration adopts **formulation 2 — entry / no-entry, long or flat**,
which is the frame the deployed book already trades. A long/short version
would first need H36 reopened with a new spec and a stated reason.

---

## Declared design

**Family:** `info.ensemble.learned_weights`, **5 declared cells.**
Declared cells bind: running a sixth requires amending this document.

| Cell | Model | Trial? |
|---|---|---|
| A | each indicator alone | **reference, not a trial** (as in H24-H32) |
| B | equal-weighted composite | 1 |
| C | logistic regression, learned weights | 1 |
| D1 | logistic regression + L2 | 1 |
| D2 | logistic regression + L1 (sparsity) | 1 |
| E | rolling retrain, walk-forward weights | 1 |

**Indicators** (`n = 6`, all already in `features/panel.py`, all computable
from data available at *t*): `r30`, `r90` momentum; `vol_excl_current(30)`;
`ma90` trend deviation; `v7/v30` volume ratio; `upshare90` trend smoothness.

**Target:** `fwd7 > 0` — did the next 7 days rise? Long/flat framing.

**Universe / period:** the wide 40-coin universe, daily, full lake depth.

---

## Anti-leakage protocol (non-negotiable)

1. **Purged walk-forward.** Train on `[t0, t1)`, test on `[t1 + purge, t2)`.
   The purge gap is the target horizon (7 days) so no training row's forward
   window overlaps a test row.
2. **Standardisation fitted on TRAIN ONLY**, then applied to test. Fitting a
   scaler on the full sample is the classic silent leak.
3. **No forward-derived feature.** Every indicator is built by the Layer 1
   feature constructors, which are already golden-tested for this.
4. **Chronological splits only.** No shuffling, no k-fold.
5. A **poison test** must pass: injecting `fwd7` itself as an indicator must
   produce near-perfect in-sample accuracy AND be caught by the walk-forward
   harness as unavailable. If the harness cannot catch a deliberate leak, no
   result from it is admissible.

---

## Verdict bars — committed before results

**Information grade (this registration):**

- **B/C/D/E pass** only if out-of-sample accuracy CI excludes 0.50 **and**
  the composite's forward-return spread CI excludes zero, on the day-block
  bootstrap the corpus uses.
- **The incremental bar (standing project rule): C must beat B.** If learned
  weights do not beat equal weights, the hypothesis is FALSE as stated —
  the claim is specifically about *learning* the weights.
- **Stability bar:** learned weight signs must agree across at least 2/3 of
  walk-forward windows. Weights that flip sign between windows are fitting
  noise, whatever the accuracy says.
- **Ablation bar:** removing the single highest-weight indicator must
  materially degrade out-of-sample performance. If it does not, the model is
  not using it and the ensemble claim is unsupported.

**Strategy grade — explicitly NOT granted here.** Any strategy built on this
requires its own registration and must clear the standing bars: beat the
DEPLOYED system incrementally (not zero), event-driven engine as source of
truth, full costs, and DSR against the ledger total at the time.

**Failure is a result.** If learned weights do not beat equal weights, that
is recorded as a kill with the same care as a pass — and it would be the
second independent confirmation of meta-finding 4.

---

## Cost of running this

The ledger stands at 120. These 5 trials take it to **125**, which raises the
deflated-Sharpe hurdle for every future strategy claim, including the
already-borderline rotation-stop. That cost is accepted deliberately and
recorded here so it is not discovered later.
