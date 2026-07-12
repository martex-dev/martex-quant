# Hypothesis 23 — Incremental Feature Tests

Status: **BOTH FAILED (2026-07-12)** — features are redundant. Trials 83.

The graduated features must beat the information the deployed systems
already use, not zero. Both tests condition on the momentum state first.

## 23a — Shock signal, incremental to momentum (from H13)

Within symbol-days where 90d momentum is FLAT-or-negative (r90 <= 0 —
days the deployed family holds nothing): do extreme up-shock days
(z >= 2 vs 30d vol) still show higher fwd 7d than that subset's
baseline? PASS: CI > 0. If shocks only fire when momentum is already
long, the feature is redundant and dies here.

## 23b — Funding-as-confirmation, incremental to momentum (from H08/H10)

Within symbol-days where 90d momentum is POSITIVE (r90 > 0, legacy 8,
funding cache): do high-funding days (>= 90th trailing percentile)
show higher fwd 7d than mid-funding momentum days (10th-90th pct)?
PASS: CI > 0. Tests whether crowding CONFIRMS trends beyond price.

## Verdicts (2026-07-12)

- 23a shocks|momentum-flat: -0.15% (CI [-2.11%, +1.59%]) — FAIL. The
  shock edge lives entirely inside days momentum already holds; as a
  feature it is redundant. Closed.
- 23b high-funding|momentum-long: +2.01% (CI [-0.28%, +4.60%]) — FAIL,
  narrowly. Crowding does not significantly confirm trends beyond
  price. Closed (a near-miss stays closed; re-opening = new spec, new
  reason, higher ledger).
