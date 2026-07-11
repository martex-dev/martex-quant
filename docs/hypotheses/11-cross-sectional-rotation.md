# Hypothesis 11 — Cross-Sectional Momentum (Relative-Strength Rotation)

Status: UNDER TEST — kill-test stage (pre-registered before results).

## Rationale

The strongest untested family in the program: rank assets by trailing
return, hold the relatively strong. Documented across asset classes for
a century (Jegadeesh-Titman lineage); crypto studies mixed-positive.
Distinct from V2's failed BTC-vs-alts ratio: this ranks individual
assets. Our time-series cousin (hyp 02/06/07) is the deployed system.

## Known bias, stated first

Our 8-symbol universe is survivors. A "hold the winners" strategy tested
on a universe of winners flatters itself. If the kill test passes, the
strategy-grade phase must widen the universe listing-aware before any
deployment claim.

## Specification (information stage — vectorized screening is allowed
pre-engine per Phase 0 rules; the event-driven multi-asset engine is
REQUIRED before any strategy-grade verdict)

- Daily closes, all 8 symbols, dates with >= 6 symbols listed.
- Each day: rank symbols by trailing L-day return, L in {30, 90} (FIXED,
  2 values only).
- Spread_t = EW mean forward-7d return of TOP-2 minus BOTTOM-2 ranked.
- PASS bar: spread > 0 with 95% block-bootstrap CI (30d blocks)
  excluding zero at >= 1 of 2 lookbacks, AND the other lookback's point
  estimate also positive. Anything less: FAIL.
- Trial ledger: +2 -> 52 (49 + 3 from hyp 10... ledger updated in
  CLAUDE.md as the single source of truth).

## If PASS

Graduates to strategy-grade: multi-asset event-driven engine build,
costs, walk-forward K/L selection, widened universe, DSR vs full ledger
— the V2-M2 build finally earns its justification.

## Verdict

(after the run)
