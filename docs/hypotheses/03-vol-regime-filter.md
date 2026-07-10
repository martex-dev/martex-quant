# Hypothesis 03 — Volatility-Regime-Filtered Momentum (Daily)

Status: UNDER TEST (pre-registered before results).

## Hypothesis and rationale

Momentum's worst losses cluster in high-volatility regimes (crash
whipsaws, forced deleveraging, V-reversals). If true, gating momentum by
a calm-volatility condition should cut drawdown more than it cuts return,
raising Sharpe. This is a FILTER hypothesis: it lives or dies relative to
hypothesis 02, not relative to buy-and-hold alone.

## Specification

Hypothesis 02's daily momentum (same L grid: 7/14/30/60/90/180), gated:
long only when 30d realized vol < 90d realized vol (calm regime). The vol
windows are FIXED, not tuned — the trial count stays 6. Same walk-forward
protocol and costs as hypothesis 02.

## Expected failure modes

Vol gating can amputate the best momentum days (rallies out of panic
bottoms are high-vol); the gate adds turnover (regime flips force exits);
in crypto, calm regimes can be the *chop* regimes where momentum whipsaws.

## Pre-registered verdict standard

SURVIVES only if, versus hypothesis 02 on the same OOS spans: higher
median Sharpe AND materially lower median max drawdown, plus DSR > 0.95
(n_trials=6) against B&H. Spec #3 on this dataset.

## Results

(filled by scripts/phase3_studies.py --study vol-filter)
