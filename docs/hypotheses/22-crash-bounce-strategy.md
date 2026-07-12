# Hypothesis 22 — Crash-Day Alt Bounce (strategy-grade)

Status: UNDER TEST (pre-registered before the run). Trials +2 -> 81.

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

## Verdict

(after the run)
