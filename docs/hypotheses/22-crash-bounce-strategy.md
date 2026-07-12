# Hypothesis 22 — Crash-Day Alt Bounce (strategy-grade)

Status: **ELIGIBLE — paper trading since 2026-07-12.** Trials 81.

## Claim (from H19's information result)

After BTC falls more than 3% in a day, altcoins outperform the next day
(+0.82% info-level). As a STRATEGY: hold an equal-weight basket of all
listed alts for exactly one day after each BTC crash day, flat otherwise.

## Specification (ZERO tunable parameters)

- Signal at close of day t: BTC daily return < -3% (threshold fixed in
  H19's pre-registration, not re-tuned).
- Position: equal-weight ALL listed non-BTC coins of the wide universe,
  weights sum to 1; entered at open t+1, exited at open t+2 (engine's
  standard one-bar latency, full cost model).
- Engine: multi-asset event-driven backtest, full lake depth.

## Pre-registered bars (paper eligibility — both required)

1. Mean net return of held days > 0 with a 95% block-bootstrap CI
   excluding zero (costs already inside the engine).
2. Annualized net contribution of the whole stream >= +3%/yr.
Prop-sim reported descriptively (an ~85%-flat stream cannot pass an
eval alone; the deployment shape would be an overlay/sleeve).

## Verdict (2026-07-12, engine-grade, 3,248 days, 11,084 fills)

BOTH BARS PASS: mean net held-day return +0.441% (CI [+0.168%, +0.742%],
727 held days — initial attribution counted exit days only, corrected
same day, conservative direction), annualized net +32.1%/yr, Sharpe
0.89, MDD -47.8%. Zero tunable parameters. Deployment shape: overlay/
sleeve (flat ~78% of days; cannot pass an eval standalone — deep MDD
from crash cascades means any live sizing must be fractional). Third
paper account opened (data/paper/crash-bounce/, wide-universe alts,
nightly task runs all three).
