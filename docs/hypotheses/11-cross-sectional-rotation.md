# Hypothesis 11 — Cross-Sectional Momentum (Relative-Strength Rotation)

Status: **PASSED the kill test (2026-07-11)** — graduates to strategy-grade.

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

## Verdict (2026-07-11, ~2,950 daily rebalance dates)

PASS — cleanly, on both lookbacks:
- L=30d: top2-minus-bottom2 fwd-7d spread +0.823%, CI [+0.082%, +1.548%]
- L=90d: +1.021%, CI [+0.154%, +2.049%]

Relative strength persists cross-sectionally in this universe. Next:
strategy-grade phase — multi-asset event-driven engine (design first,
per process), costs, walk-forward K/L selection, LONG-ONLY variant
prioritized (short leg is both survivor-biased and funding-costly),
widened listing-aware universe, DSR vs the full ledger. Survivorship
caveat from the pre-registration REMAINS OPEN and must be addressed
before any deployment claim.

## Strategy-grade specification (pre-registered 2026-07-11, BEFORE the run)

- **DualMomentumRotation**: each day rank the 8 symbols by trailing
  L-day return; hold the TOP-2 equal-weight, but only slots whose
  trailing return is POSITIVE (absolute-momentum gate — combines the
  validated time-series result with the passed cross-sectional test);
  gated-out slots sit in cash. Long-only. K=2 FIXED.
- L selected by walk-forward: 365d train, 90d test, grid {30, 90} ONLY.
- Multi-asset event-driven engine (one-bar latency, standard cost
  model), daily bars, full lake depth.
- Verdict bars (candidate grade):
  1. OOS portfolio Sharpe >= the deployed vol-target candidate's on the
     common window, OR Sharpe within 15% of it with return correlation
     < 0.7 (diversification value justifies a second engine);
  2. prop-sim (real firm 1-step static rules) pass rate >= 35% at some
     sizing;
  3. DSR vs full ledger reported honestly (0.95 remains the absolute
     validation bar; candidate grade does not require it, deployment of
     real money does).
- Paper trading eligibility: meets bars 1 AND 2 -> joins the paper
  stable alongside vol-target.
- Trial ledger: +3 (2 lookbacks + gated spec) -> 55.
- Survivorship caveat REMAINS OPEN (universe = survivors); recorded on
  every result until a listing-aware wide universe re-run exists.

## Strategy-grade results, RAW variant (2026-07-11)

Walk-forward OOS 2,880d (~7.9y): **Sharpe 0.98, CAGR +60%, DSR 0.888 vs
55 trials — the strongest evidence in the program**; correlation with the
deployed V1 stream only 0.34 (true diversifier); V1 Sharpe on the same
overlap 0.74. BUT max drawdown -76% and high daily vol -> real-firm
prop-sim pass 28-31% at ALL sizings (bar: 35%). Bar 1 PASS, bar 2 FAIL:
**raw variant NOT eligible for paper.**

## SIZED variant (pre-registered 2026-07-11 BEFORE its run; +1 trial -> 56)

VolTargetRotation: identical signal and walk-forward protocol; selected
basket's weights scaled by min(1, 0.30 / realized 30d basket vol)
(target and window FIXED — the exact cure hyp 06 applied to hyp 02/07).
Same two bars. If it passes both -> paper eligible.
