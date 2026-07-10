# Hypothesis 01 — Time-Series Momentum (TSMOM)

Status: UNDER TEST. Nothing here is a validated edge until the walk-forward
results section at the bottom says so.

## Market hypothesis

An asset's own trailing return predicts its near-future return: assets that
went up over the past weeks-to-months continue up more often than chance,
and vice versa.

## Why might the edge exist?

- **Slow information diffusion**: large flows (funds, treasuries, ETF
  allocations) execute over weeks, not instants; price drifts while they do.
- **Herding / feedback**: trends attract trend-followers, extending moves
  beyond fair value before any correction.
- **Risk transfer premium**: momentum harvesting is short volatility spikes;
  its long flat/losing stretches are the price of the premium.
- It is the most robust documented anomaly across asset classes and a
  century of data (Moskowitz, Ooi & Pedersen 2012), which raises the prior —
  but crypto post-2022 is a professionalized market, so the prior is modest.

## Where it should work / fail

- **Works**: sustained directional regimes (2020-21 bull, 2022 bear); daily
  to weekly horizons; liquid majors where costs are small vs. signal.
- **Fails**: choppy ranges (whipsaw death by a thousand fills); sharp
  V-reversals (momentum is always late); very short horizons where fees and
  spread dominate; regime breaks after structural changes.

## Strategy specification (deliberately minimal: ONE parameter)

Long 100% when the trailing `L`-bar close-to-close return is positive,
flat otherwise. Long/flat only (spot; no borrow modeling yet).
Grid: L ∈ {168, 336, 504, 720, 1440, 2160} hours (1w, 2w, 3w, 30d, 60d, 90d).

## Risk rules (research phase)

Engine-enforced costs: 10 bps taker fee, 1 bp half-spread, volume-impact
slippage, one-bar latency. Full risk policies (sizing, drawdown caps) are
Phase 4; research runs use fixed full exposure so results are interpretable.

## Validation plan

1. Walk-forward: select L on each 1-year train window (by Sharpe), apply to
   the following 90-day test window, roll. Only stitched OUT-OF-SAMPLE
   results count.
2. Benchmark: buy-and-hold over the identical OOS span.
3. Multiple-testing control: probabilistic Sharpe ratio of the OOS result
   against the expected max Sharpe of 6 unskilled trials (deflated Sharpe).
4. Parameter sensitivity: an edge that exists only at one L is noise.
5. Verdict standard: pre-registered here — the hypothesis SURVIVES only if
   the stitched OOS result beats buy-and-hold risk-adjusted (higher Sharpe
   or comparable Sharpe with materially lower drawdown) AND the deflated
   Sharpe probability exceeds 0.95 AND the result is not driven by a single
   window or single lookback. Anything less: REJECTED or INCONCLUSIVE.

## Results

(to be filled by scripts/tsmom_study.py — see bottom of file)
