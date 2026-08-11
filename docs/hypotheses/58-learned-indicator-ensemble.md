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

---

## VERDICT — 2026-08-11, `scripts/h58_ensemble_study.py`

**H58 KILLED at the information stage. Ledger 120 -> 125.**

Panel: 64,484 symbol-days over 3,250 dates. 13 purged walk-forward windows
(2y train / 7d purge / 6m test), scaler fitted on train only.

**Poison test passed first, and it earned its keep.** The first run REFUSED
to report any result, because the leak alarm could not demonstrate
sensitivity: it was measuring correlation against the binary target, and a
variable correlates with its own sign at only ~0.8, so even a perfect leak
would not have tripped a 0.95 alarm. Fixed to measure against the continuous
outcome; `fwd7` injected as a predictor is now caught twice (by name, and at
|r|=1.000), and the declared feature set is clean.

| Cell | Accuracy | fwd7 spread | 95% CI | |
|---|---|---|---|---|
| B equal-weighted | **0.5213** | **+2.79%** | [+0.83%, +4.90%] | **SIGNAL** |
| C learned weights | 0.5062 | −0.56% | [−2.06%, +0.82%] | noise |
| D1 learned + L2 | 0.5062 | −0.57% | [−2.05%, +0.79%] | noise |
| D2 learned + L1 | 0.5063 | −0.54% | [−2.02%, +0.89%] | noise |
| E rolling retrain | 0.5109 | +0.38% | [−1.02%, +1.85%] | noise |

**BAR 1 — C must beat B: FAIL, and not narrowly.** Equal weighting scores
0.5213 against learned 0.5062, and more decisively the equal-weighted
composite's forward-return spread is a clear SIGNAL (+2.79%, CI above zero)
while every learned variant is indistinguishable from noise. Regularisation
(D1, D2) and rolling retraining (E) did not rescue it.

The registered claim was specifically that *learning* the weights helps. It
does not. **The hypothesis is false as stated.**

**BAR 2 — stability: PASSED, which makes the kill more interesting.** 6/6
features held their weight sign in at least 2/3 of windows, four of them at
85–92%. The learned weights are *stable*; they are simply worse. This is not
an overfitting story in the usual sense — the model converged on a
consistent, reproducible answer that trades badly.

**BAR 3 — ablation: passed.** Dropping the top-weighted feature (`ma90_dev`,
mean weight −0.376) degrades accuracy 0.5062 -> 0.4983, so the model was
genuinely using it.

### Why it failed, stated as a lead rather than a conclusion

Logistic regression maximises likelihood on the binary **direction** target.
The trading outcome is the **return spread**. Those are not the same
objective, and the results separate them cleanly: the learned model is a
marginally better direction classifier that selects materially worse trades.
Equal weighting, which optimises nothing, produced the tradeable signal.

This is a lead for a future registration, not a finding here.

### Ledger context

This is the **second independent confirmation of meta-finding 4**
(info-signal ≠ strategy improvement), and it now has a sharper form: a
composite that is significant unweighted can be destroyed by fitting weights
to the wrong objective. H33 died going from info to strategy grade; H58 dies
one step earlier, at the weighting itself.

**Reference, not a trial:** `r90` alone produced a significant NEGATIVE 7-day
spread (−2.11%, CI [−4.28%, −0.17%]). At the 7-day horizon, 90-day momentum
was contrarian over this sample. That contradicts nothing — the deployed book
trades r90 cross-sectionally at longer horizons — but it is recorded because
it was measured.

### What is NOT concluded

Equal weighting is **not** hereby a validated strategy. B's +2.79% spread is
an information-level result on a reference cell; turning it into a strategy
requires its own registration, the event-driven engine, full costs, an
incremental bar against the deployed system, and DSR against a ledger that is
now 125.

### Post-run change to the harness, and its verification

After the result was recorded, two changes were made to `research/ensemble.py`:
a mypy-strict fix to the accuracy accessor, and replacing a deprecated polars
`is_in` call with the `.implode()` spelling. Neither is allowed to be taken on
trust after publication, so the study was re-run end to end and reproduced
**every figure above digit for digit** — all six references, all five cells,
all three bars, all six stability shares.

`tests/test_ensemble.py` was added at the same time and tests the harness on
its safety properties rather than its outputs: the purge gap, non-overlapping
test slices, refusal of forward-named features, leak-alarm sensitivity to a
near-copy of the outcome, and — the decisive pair — a **null control** that
must find no skill in pure noise and a **positive control** that must recover
a planted signal. A harness failing the first is leaking; one failing the
second would make every kill it produces meaningless.
