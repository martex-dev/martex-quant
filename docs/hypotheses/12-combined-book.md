# Hypothesis 12 — Combined Book (50/50 Momentum + Rotation)

Status: **NOT ELIGIBLE (2026-07-12)** — fails the Sharpe bar; no third
paper account. Trial ledger: 57.

## Rationale

The two paper survivors are structurally different return sources with
OOS correlation 0.35: vol-target momentum (absolute trend, 8 slots,
long/flat) and sized rotation (relative strength, top-2, vol budget).
Portfolio theory's one free lunch: blending imperfectly correlated
streams keeps the average return while cancelling part of the drawdowns.

## Specification (FIXED — no tunable parameters introduced)

Half the account runs EXACTLY the vol-target momentum book; the other
half runs EXACTLY the sized rotation book; per-symbol positions are the
sum of the two sleeves' targets; the 50/50 capital split rebalances
daily. Each sleeve keeps its own parameter re-selection, unchanged.

## Pre-registered bars (candidate grade -> paper eligible)

1. On the common OOS window: combined Sharpe > the best single sleeve,
   OR within 5% of the best sleeve with max drawdown lower than BOTH.
2. Real-firm prop-sim (1-step 5k static, $51.80): pass >= 45% at some
   sizing.
3. DSR vs 57-trial ledger reported honestly.

## Expected failure modes

The common window is only ~4.7y (SOL-limited); the 50/50 split is a
choice, not an optimum (deliberately NOT optimized — weight optimization
on 2 assets with 4.7y of data is curve-fitting with extra steps); both
sleeves share crypto beta, so crisis correlation will exceed 0.35
exactly when it hurts most.

## Verdict (2026-07-12, common 4.7y OOS window, timestamp-joined)

**Correction recorded first**: the previously reported sleeve correlation
of 0.35 (hyp 11 results) came from a tail-count alignment bug; the
correct timestamp-joined correlation is **0.77**. Hyp 11's eligibility
is unaffected (it passed via the Sharpe bar), but its "diversifier"
framing was overstated and is retracted.

Results: V1 Sharpe 0.53 / MDD -25.1%; rotation 0.78 / -42.8%; combined
0.72 / -31.6%; combined prop pass 48.0% @ 0.5x. Bar 1 FAILS (0.72 <
0.95 x 0.78 and MDD not better than both); bar 2 passes. At rho=0.77 the
blend averages its parents instead of insuring them — both sleeves are
crypto-long momentum variants sharing the same bleed periods.

Disposition: no combined paper account. The combined-book code remains
(tested) for a future genuinely-uncorrelated second engine — the carry
strategy (market-neutral, post-eval build) is the natural candidate.
Lesson kept: diversification claims require timestamp-joined
correlation on the common window, nothing less.
