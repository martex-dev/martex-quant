# Wide-Universe Data Project

Status: IN PROGRESS (2026-07-12). Selection rule and re-test bars
pre-registered here BEFORE any data is pulled.

## Purpose

Attack the survivorship caveat attached to every result to date
(especially rotation, hyp 11), widen rotation's menu, and unlock
breadth (and later regime/ML) research.

## Universe selection rule (objective, reproducible)

All Binance SPOT */USDT markets, minus stablecoin bases (USDC, FDUSD,
TUSD, DAI, USDP, EUR-likes) and leveraged tokens (UP/DOWN/BULL/BEAR
suffixes), ranked by current 24h quote volume; take the TOP 40, union
with the existing 8. Daily bars, full listing depth.

## Honesty statement on what this does and does not fix

This universe includes coins that collapsed 90-99% and still trade
(the FTT/LUNC class) — a large slice of the survivorship spectrum our
8-coin universe missed. It does NOT include coins Binance fully
delisted (their history is not served); a point-in-time universe needs
a paid vendor. So: survivorship is MITIGATED, not eliminated, and every
verdict says so. Selection-by-today's-volume is itself mildly
survivor-tilted; accepted and disclosed.

## Pre-registered re-test (rotation on the wide universe)

Same spec as hyp 11's sized variant: VolTargetRotation, K=2, L selected
by walk-forward from {30, 90}, 365d train / 90d test, standard costs.
One added variant: K=5 (wider book for the wider menu). Trials: +2 ->
ledger 65.

Bars:
1. SURVIVES if wide-universe OOS Sharpe >= 85% of the 8-coin version's
   Sharpe on the same OOS span (performance does not collapse when the
   survivor tailwind is diluted), for at least one of K=2 / K=5.
2. Real-firm prop-sim pass >= 45% at some sizing for that variant.
If both hold, the survivorship caveat is DOWNGRADED (not erased) and
the wide variant becomes a candidate to replace the 8-coin paper spec
(a deliberate, separate decision). If bar 1 fails, hyp 11's results are
flagged as survivor-inflated and rotation stays paper-only indefinitely.

## Verdict (2026-07-12, 40-symbol universe, all 48 datasets 0 errors)

**SURVIVORSHIP CAVEAT DOWNGRADED — and the program's first ABSOLUTE
VALIDATION.** Rotation got STRONGER on the wider universe:

- K=2: OOS 2,880d, Sharpe 1.10 (8-coin: 0.90), CAGR +31.2%, MDD -58.0%,
  prop pass 62.9% @ 0.5x, **DSR 0.990 vs the 65-trial ledger — the
  first result above the pre-registered 0.95 validation bar.**
- K=5: Sharpe 0.95, DSR 0.910, prop 55.0% — robust across widths.

Cross-sectional edges feed on breadth: more coins = better ranking
discrimination. Residual honesty: fully-delisted coins are still
absent (unmeasurable without a paid point-in-time vendor), so a thin
slice of survivorship remains; the verdict language stays 'validated
on the best universe an honest retail dataset allows'.

Disposition: rotation paper spec SWITCHED to the wide universe (K=2)
2026-07-12; the 1-day 8-coin record archived
(data/paper/rotation/archive-8coin). First wide decision: held DEXE +
SYN at 13% combined — vol budget correctly throttling extreme movers.
