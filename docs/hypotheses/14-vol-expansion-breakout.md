# Hypothesis 14 — Volatility-Expansion Breakout

Status: **FAILED (2026-07-12)** — compression adds nothing.

## Claim

Markets compress before they move: a large move that ERUPTS FROM
COMPRESSION carries more directional follow-through than the same-size
move without compression. (Different question from hyp 03's rejected
"filter momentum by vol level".)

## Specification (FIXED)

Pooled 8-symbol daily panel, 2017+.
- Compression: trailing 10d realized vol in the BOTTOM 20% of its own
  trailing-365d distribution.
- Expansion trigger: |today's return| > 2 x trailing 10d vol.
- Signal day = compression AND trigger; direction = sign of the move.
- Primary metric: mean DIRECTIONAL forward 7d return (fwd return x
  direction) of signal days. PASS requires BOTH:
  1. signal days' directional fwd7 > 0, 95% block-bootstrap CI excl. 0;
  2. it exceeds the directional fwd7 of matched trigger-days WITHOUT
     compression (the increment is the claim), CI of the difference
     excluding 0.
- 1d/3d descriptive.

Trial ledger: +2 -> 63.

## Verdict (2026-07-12)

FAIL on both bars: signal days' directional fwd7 +1.10% with CI
[-0.14%, +1.97%] (misses), and the increment over expansion-WITHOUT-
compression is -0.76% (CI [-3.49%, +1.60%]) — if anything, compression
made breakouts slightly WORSE, not better. The 'coiled spring' story is
folklore in this data. Closed.
