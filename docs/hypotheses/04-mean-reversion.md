# Hypothesis 04 — Short-Horizon Mean Reversion (1h)

Status: UNDER TEST (pre-registered before results).

## Hypothesis and rationale

Liquidity provision premium: sharp short-horizon selloffs overshoot
(stop cascades, liquidations, panic) and partially revert as makers
refill the book. The buyer of the overshoot earns the reversion — if it
survives fees, which Phase 0 flagged as this family's likely killer.

## Specification

1h bars. Long while close < SMA(168h) − k·std(168h), flat on recovery.
Window FIXED at 168h (1 week); grid is band width k ∈ {1.0, 1.5, 2.0,
2.5} (4 trials). Walk-forward: 1y train, 90d test. Same costs.

## Expected failure modes (stated up front)

- **Falling knives**: the entry condition is exactly "price is crashing";
  it holds until recovery. In a trending bear (2022) this is repeated
  catastrophic entries. Genuine risk of the worst result of all studies.
- Costs: more frequent trading than daily momentum.
- PRE-REGISTERED EXPECTATION: likely REJECTED. Testing it anyway because
  a documented negative result on the family is Phase 3 deliverable.

## Pre-registered verdict standard

Same structure: broad risk-adjusted B&H outperformance AND DSR > 0.95
(n_trials=4) AND parameter stability. Spec #4 on this dataset.

## Results

(filled by scripts/phase3_studies.py --study meanrev)
