# Hypothesis 13 — Single-Day Shock Persistence

Status: **1/4 buckets carries signal (2026-07-12)** — extreme UP shocks
continue; graduated to the feature queue.

## Claim

Large ONE-DAY moves carry information about the following week — either
continuation (herding into the shock) or exhaustion (overreaction).
Distinct from the validated multi-week momentum: this is event-scale
autocorrelation, and the data decides direction.

## Specification (FIXED)

Pooled 8-symbol daily panel, 2017+. Shock size z = today's return /
trailing 30d vol (vol excludes today). Buckets: extreme up (z >= 2),
moderate up (1 <= z < 2), moderate down (-2 < z <= -1), extreme down
(z <= -2); baseline = quiet days (|z| < 1). Primary: forward 7d return
of each bucket minus baseline, 95% block-bootstrap CI (30d date blocks,
cross-section intact). Two-sided; a bucket "carries signal" if its CI
excludes zero. 1d/3d horizons descriptive only.

Trial ledger: +4 (four buckets at the primary horizon) -> 61.

## Verdict (2026-07-12, 23,209 symbol-days)

- **Extreme up (z>=2, n=924): +3.54% extra over the next 7d, CI
  [+1.25%, +5.99%] — clear CONTINUATION signal.** No exhaustion.
- Moderate up/down and extreme down: noise (all CIs straddle zero;
  extreme down leans continuation but does not qualify).

Fourth independent test where continuation beats reversal in crypto
(funding, basis, dominance quadrants, now shocks). Disposition:
graduated as a CANDIDATE FEATURE, not a strategy — an extreme-up-day
overlay must beat the deployed price-momentum baseline (which already
captures much of this: a +2-sigma day often flips short-lookback
momentum positive) in a pre-registered incremental test before any
deployment. Queued on the backlog next to positioning-as-confirmation.
