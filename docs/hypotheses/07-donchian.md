# Hypothesis 07 — Donchian Channel Breakout (Daily)

Status: **INCONCLUSIVE-POSITIVE — strongest evidence of all families**
(2026-07-11). Portfolio DSR 0.821 vs all-38-trials benchmark; fails the
0.95 absolute bar.

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

## Results (2026-07-11, extended 2017+ data)

Per symbol (own full history, 6-trial DSR): **6/8 beat B&H on Sharpe,
median DSR 0.947** — the best per-symbol evidence of any family. SOL:
Sharpe 1.38, DSR 0.997; DOGE 0.91/0.989; ETH 0.78/0.967. Time in market
only 25-42% (it sits out ranges), yet returns are B&H-competitive.

Equal-weight portfolio, common 4.7y OOS window, all-38-trials benchmark:
- Sharpe 0.68, CAGR +10.3%, MDD -38.7%, **DSR 0.821**
- Prop-sim best: GENERIC-A @ 1.0x -> 29.1% pass, median 23 days,
  EV +$1,285 per attempt, EV/day +$55.9

Verdict: fails absolute validation (0.821 < 0.95) but carries the
strongest statistical evidence in the project. Known cost confirmed:
deep MDD (-39% portfolio; ADA/DOGE -87/-90% single-symbol) — the wide
channel exit gives back large open profits. Selected as the
evaluation-stage engine in the final selection (see
docs/research/final-selection.md).
