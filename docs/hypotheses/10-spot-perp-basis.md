# Hypothesis 10 — Spot-vs-Perp Basis as a State Variable

Status: **FAILED (2026-07-11)** — significantly BACKWARDS, same
pattern as hypothesis 08.

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

## Verdict (2026-07-11, 17,899 symbol-days)

FAIL: 7d LOW-minus-HIGH = -2.61%, CI [-4.88%, -0.12%] — the interval
excludes zero on the WRONG side, 2/8 symbols positive. High premium was
followed by HIGHER returns (+4.20% vs +1.59% fwd 7d; +14.8% vs +6.1%
at 30d). Third data point in the same lesson (with hyp 08 and the core
momentum results): in crypto, crowded bullish positioning accompanies
trends that continue; fading it is systematically wrong on average.

Post-hoc observation, worth exactly nothing until pre-registered: the
REVERSED (momentum-flavored) basis signal shows significance here, but
it was not the registered claim, and its incremental value over plain
price momentum (already deployed) is the real bar it would face. Closed.
