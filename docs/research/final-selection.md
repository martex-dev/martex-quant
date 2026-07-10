# Final Selection — Extended Data (2017+), All Families Re-Run (2026-07-11)

Everything re-tested on data back to each symbol's Binance listing
(BTC/ETH Aug 2017; 3,249 daily bars, ~79k hourly bars). Portfolio
comparisons use the common 4.7y OOS window (limited by SOL's 2020
listing — includes the 2022 bear). Trial accounting: **38 specs**.
Reproducible: scripts/final_selection.py, scripts/phase3_studies.py.

## Scoreboard (all seven hypotheses, extended data)

| # | Family | Verdict on extended data |
|---|---|---|
| 01 | TSMOM 1h | REJECTED — DSR improved (median 0.952) but 3/8 beat B&H, -90%+ MDDs |
| 02 | TSMOM 1d | Positive; per-symbol median DSR 0.911; superseded by 06/07 |
| 03 | Vol-gated TSMOM | REJECTED (still worse than 02) |
| 04 | Mean reversion 1h | REJECTED — 0/8, median DSR 0.036 |
| 05 | Carry | Premium confirmed (5.8-7.9%/yr gross); infra queued |
| 06 | **Vol-target TSMOM** | Survives relative standard; MDD -20%, best prop pass 38.4% |
| 07 | **Donchian breakout** | Strongest evidence: per-symbol median DSR 0.947, portfolio 0.821 |

## Finalists, portfolio level (common 4.7y OOS, all-38-trials DSR benchmark)

| | CAGR | Sharpe | MDD | DSR | Best prop config | Pass % | Median days | EV/attempt | EV/day |
|---|---|---|---|---|---|---|---|---|---|
| daily-tsmom | +12.1% | 0.67 | -39% | 0.592 | GEN-A @1.0x | 28.6% | 15 | +$1,260 | **+$84** |
| vol-target | +6.7% | 0.74 | **-20%** | 0.660 | GEN-A @1.0x | **38.4%** | 55 | +$1,751 | +$32 |
| donchian | +10.3% | 0.68 | -39% | **0.821** | GEN-A @1.0x | 29.1% | 23 | +$1,285 | +$56 |

(EV at assumed funded-account value $5k; EOD-trailing approximation —
all pass rates are upper bounds.)

## THE SELECTION

**Two-stage deployment of one system:**

1. **Evaluation stage: Donchian breakout** — equal-weight 8 symbols,
   channel N re-selected each 90d by walk-forward (grid 10-120d), full
   (1.0x) sizing. Chosen over daily-tsmom's higher EV/day because its
   statistical evidence is decisively stronger (DSR 0.821 vs 0.592) —
   an EV/day edge built on a weaker edge estimate is paying yourself in
   assumptions. Pass 29.1% (CI 28.2-30.0%), median 23 days, EV +$1,285
   per attempt.
2. **Funded stage: switch to vol-target momentum** (30% vol target) —
   MDD -20%, the profile that survives trailing drawdowns and collects
   payouts. Passing is a sprint; staying funded is survival.

## Why not "more aggressive"

- 2x sizing was simulated: pass rates FALL (busts outrun the target).
  The trailing-drawdown geometry, not courage, sets maximum aggression.
- The eye-watering per-symbol numbers (DOGE TSMOM +11,545% over 7y) come
  with -77..-92% drawdowns — any prop account is dead in the first month
  of that path. They are not usable aggression.

## Standing caveats (unchanged and non-negotiable)

No family passed absolute validation (DSR > 0.95 vs all 38 trials);
Donchian at 0.821 is strong-but-not-proof. Real prop-firm rules and
automation policies remain UNVERIFIED — blocking item before any fee.
Evals are futures; this system trades crypto spot. Next honest steps:
paper trading (Phase 5) and verifying a real firm's ruleset, not adding
more strategy families — family #8 would raise the noise ceiling for
everything, including the current leaders.
