# Hypothesis 07 — Donchian Channel Breakout (Daily)

Status: UNDER TEST (pre-registered before results).

## Hypothesis and rationale

Breakouts to N-day highs mark the moments trends START or resume —
entering there captures more of each trend than lookback-return momentum,
which is late by construction. The asymmetric exit (half-length low
channel) rides winners and cuts losers — the aggressive-but-managed
profile requested for the prop path. This is the oldest documented trend
system (Donchian/turtles); its economic story is the same as TSMOM's.

## Specification

Daily bars, long when close > prior N-day high, exit when close < prior
(N/2)-day low. Grid: N ∈ {10, 20, 40, 55, 80, 120} (6 trials — 55 is the
classic turtle number). Long/flat. Walk-forward: 365d train, 90d test.

## Expected failure modes

False breakouts in ranges (death by whipsaw — worse than TSMOM's because
entries are chase-y); the wide exit gives back large open profits at
trend ends.

## Pre-registered verdict standard

Same as hypothesis 02/06: broad risk-adjusted B&H outperformance, DSR >
0.95 (n_trials=6), parameter stability; prop-sim pass rate reported for
the final selection. Trial accounting: specs #07.

## Results

(filled by scripts/phase3_studies.py --study donchian)
