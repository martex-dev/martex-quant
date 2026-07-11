# Hypothesis 10 — Spot-vs-Perp Basis as a State Variable

Status: UNDER TEST (pre-registered before results).

## Rationale

The perp's premium/discount to spot is the LEVEL of speculative pressure
(funding, which died as a signal in hypothesis 08, is the flow derived
from it). Claim: deep DISCOUNT (perp below spot — fear, deleveraged
positioning) predicts stronger forward spot returns; steep PREMIUM
predicts weaker. Honest prior: LOW — mechanically cousin to hypothesis
08, which failed with opposite-leaning point estimates. Tested because
level and flow can carry different information and the test costs hours.

## Specification (mirrors hypothesis 08's machinery)

- Data: Binance USDT-perp DAILY closes (fetched from each contract's
  launch, cached data/perp/), joined to spot daily closes from the lake.
- Basis_t = perp_close / spot_close - 1, per symbol-day.
- Signal state: trailing-90d percentile of basis. LOW <= 10th pct,
  HIGH >= 90th. Window/thresholds FIXED.
- Primary: pooled E[fwd 7d spot | LOW] - E[fwd 7d | HIGH] > 0 with 95%
  block-bootstrap CI (30d blocks) excluding zero AND >= 5/8 symbols
  positive. Descriptive: 1d, 30d.
- Trial ledger: +3 -> 50.

## Verdict

(after the run)
