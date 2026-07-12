# Hypotheses 15-21 — Overnight Kill-Test Batch

Status: UNDER TEST (pre-registered before any test runs, 2026-07-12
night). All on lake data. Daily panels use the WIDE 40-coin universe;
the session test uses the legacy 8 (only they have hourly history).
Shared machinery: 95% moving-block bootstrap (30d date blocks,
cross-section intact). Trial ledger: +13 -> 78.

## H15 — Weekly crash bounce (+2 trials)

Events: trailing 7d return <= -15%. (a) E[fwd 7d] minus all-days
baseline — the bounce claim is positive, reported two-sided. (b) Among
crash days: vol-falling (10d vol < its value 7d earlier) minus
vol-rising. PASS per claim: CI excludes zero.

## H16 — Momentum acceleration, cross-sectional (+2 trials)

Daily, wide universe, days with >= 10 rankable coins. (a) rank by 7d
return, top2-minus-bot2 fwd 7d spread. (b) rank by acceleration
a = r(0..7d) - r(7..30d). PASS: CI > 0. CONDITIONAL FOLLOW-UP
(pre-registered): if either passes AND its spread point estimate
exceeds the 30d-ranking spread computed identically, run strategy-grade
wide rotation with L grid {7, 30, 90} (+1 trial); bars: Sharpe > 1.10
(current wide baseline) and prop pass >= 45%.

## H17 — Fallen-angel recovery (+1 trial)

Events: >= 50% below trailing 365d peak AND trailing 14d return >=
+20%. E[fwd 30d] minus baseline. PASS: CI excludes zero.

## H18 — Trend overextension / exhaustion (+2 trials)

Stretch = close / 90d MA - 1, trailing-365d percentile >= 0.95.
E[fwd 7d] and E[fwd 30d] minus baseline. The exhaustion claim is
NEGATIVE diffs; two-sided reporting (the continuation theme predicts
the opposite — the data referees).

## H19 — BTC -> alt lead-lag (+2 trials)

Alt-only panel, NEXT-day alt return conditioned on BTC's today: (a)
BTC > +3% vs BTC quiet (|r| < 1%); (b) BTC < -3% vs quiet. PASS: CI
excludes zero.

## H20 — Session effects (+3 trials)

Hourly panel (legacy 8): mean hourly return within UTC sessions
[00-08) Asia, [08-16) EU, [16-24) US, each vs the other two, two-sided.

## H21 — Volume-conviction momentum (+1 trial)

Among symbol-days ranked top-2 by 30d return (rotation's picks): split
by volume expansion (7d avg volume / 30d avg volume > 1 vs <= 1);
difference in fwd 7d. PASS: CI excludes zero (either direction is
informative for the rotation filter).

## Verdicts

(after the run)
