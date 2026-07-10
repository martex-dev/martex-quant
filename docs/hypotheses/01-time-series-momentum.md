# Hypothesis 01 — Time-Series Momentum (TSMOM)

Status: **REJECTED as specified** (2026-07-11). See Results.

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

## Results (2026-07-11, scripts/tsmom_study.py, data through 2026-07-10)

~3 years of stitched OOS per symbol (12 windows x 90d), costs included:

| symbol | OOS ret | OOS Sharpe | OOS MDD | B&H ret | B&H Sharpe | DSR |
|---|---|---|---|---|---|---|
| BTCUSDT | +63.4% | 0.67 | -31.0% | +109.6% | 0.76 | 0.612 |
| ETHUSDT | +26.1% | 0.40 | -50.5% | -4.7% | 0.29 | 0.354 |
| BNBUSDT | +19.0% | 0.36 | -52.7% | +133.4% | 0.79 | 0.364 |
| SOLUSDT | +5.5% | 0.34 | -84.6% | +258.2% | 0.92 | 0.577 |
| XRPUSDT | -24.1% | 0.15 | -73.2% | +132.0% | 0.75 | 0.475 |
| ADAUSDT | +7.3% | 0.35 | -69.7% | -42.7% | 0.24 | 0.422 |
| DOGEUSDT | -44.3% | 0.07 | -82.1% | +13.5% | 0.50 | 0.304 |
| LTCUSDT | -65.5% | -0.38 | -74.8% | -54.1% | 0.03 | 0.082 |

Verdict against the pre-registered standard:
- Beat B&H on Sharpe: 2/8 (ETH, ADA) — fails "broad" requirement.
- Median deflated Sharpe probability: 0.393; best 0.612 — nowhere near
  the 0.95 bar. The two B&H "wins" are indistinguishable from picking
  the luckiest of 6 lookbacks.
- Parameter instability: chosen L jumps across the grid between windows
  on every symbol — the signature of noise, not signal.

**Conclusion: long/flat TSMOM on 1h bars with lookbacks 1w-90d, as
specified here, is NOT an edge in 2022-2026 crypto majors after costs.**

What this does and does not kill:
- Killed: this exact specification. Do not resurrect it with tweaks and
  re-test on the same data without counting the extra trials.
- Not yet tested (each would be a NEW numbered hypothesis, and every
  additional test raises the multiple-testing bar): daily-bar momentum
  (the academic result is daily/weekly, not hourly), volatility-regime
  filtering (hypothesis family 2), vol-targeted sizing instead of
  binary long/flat, cross-sectional momentum across symbols, and carry.
