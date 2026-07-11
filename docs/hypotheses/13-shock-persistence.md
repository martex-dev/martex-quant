# Hypothesis 13 — Single-Day Shock Persistence

Status: UNDER TEST (pre-registered before results).

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

## Verdict

(after the run)
