# Hypotheses 15-21 — Overnight Kill-Test Batch

Status: **COMPLETE (2026-07-12 overnight)** — 3 signals, 4 kills;
conditional follow-up triggered (see verdicts). All on lake data. Daily panels use the WIDE 40-coin universe;
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

## Verdicts (64,484 symbol-days, wide universe)

- **H15 crash bounce: KILLED both claims** (+1.30% CI [-0.09,+2.72];
  vol-conditioning adds nothing). No bounce after weekly crashes —
  continuation world, 5th confirmation incoming below.
- **H16: 7d-return ranking SIGNALS** (+1.397%/wk top2-bot2, CI
  [+0.24,+2.76]) and beats the 30d reference (+0.869%, noise on this
  panel) -> pre-registered follow-up FIRED: wide rotation, grid
  {7,30,90}, K=2, bars Sharpe > 1.10 and prop >= 45% (+1 trial -> 79).
  Acceleration (2nd derivative): noise — killed.
- **H17 fallen-angel recovery: KILLED** (-1.90%, CI wide). Buying
  bounced losers has no premium here.
- **H18 overextension: SIGNAL — IN THE OPPOSITE DIRECTION.** Coins
  stretched >= 95th pct above their 90d MA earn MORE, not less:
  +2.83% fwd7 (CI [+0.19,+5.60]), +10.52% fwd30 (CI [+0.37,+23.63]).
  Exhaustion rejected; extension IS strength. Fifth independent
  continuation confirmation. Overlaps rotation's picks — recorded as
  supporting evidence, not a new strategy.
- **H19 lead-lag: BTC up-days lead nothing; BTC DOWN-days (<-3%) are
  followed by alts +0.82% NEXT day (CI [+0.21,+1.46]).** A 1-day
  reactive long. Costs (~0.22% round trip) leave room on paper; queued
  as a feature/mini-strategy candidate requiring its own strategy-grade
  test with costs before anything more.
- **H20 sessions: US hours (16-24 UTC) carry the drift** (+0.02%/hour
  vs others, CI excludes 0; Asia/EU flat-to-negative, noise). Too small
  per-hour to trade against costs (hourly trading is dead, hyp 01),
  but recorded as an EXECUTION note: crypto's daily drift concentrates
  in US hours.
- **H21 volume-conviction: noise** (+2.44%, CI [-0.23,+4.65]) — close,
  not qualified. Volume filter does not join the rotation spec.

## Conditional follow-up verdict (2026-07-12, +1 trial -> 79)

Wide rotation with grid {7,30,90}: **FAILS its bar** — Sharpe 0.83
(champion {30,90}: 1.10), DSR 0.920 (0.990), prop 55.6% (62.9%). The
selector chased the noisier 7d ranking in a third of windows and
degraded OOS. The 7d signal is REAL at the information level but
HARMFUL inside this strategy's selection loop. Champion spec unchanged;
7d ranking archived as an info-positive/strategy-negative finding.
