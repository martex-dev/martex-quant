# Hypothesis 02 — Time-Series Momentum, Daily Bars

Status: **INCONCLUSIVE-POSITIVE** (2026-07-11) — fails the 0.95 DSR bar.
EXTENDED-DATA UPDATE (same day, data back to each listing/2017+):
per-symbol median DSR rose 0.624 -> 0.911 (BTC 0.968, BNB 0.962,
DOGE 0.999), 5/8 beat B&H over ~7y OOS — the signal strengthened with
3x the sample, which is what a real (if modest) edge looks like. On the
common 4.7y portfolio window vs the all-38-trials benchmark: Sharpe
0.67, MDD -39%, DSR 0.592. Superseded as lead candidate by hypotheses
06/07 (see docs/research/final-selection.md).

## Hypothesis and rationale

Same economic story as hypothesis 01 (slow diffusion, herding, risk
transfer), but at the horizon where the anomaly is actually documented:
the academic TSMOM literature is a daily/weekly-bar, weeks-to-months
phenomenon. Hypothesis 01's hourly rejection does not test this. Daily
bars also trade ~24x less often, so costs bite far less.

## Specification

Long 100% when trailing L-day close return is positive, else flat. Spot,
long/flat. Grid: L ∈ {7, 14, 30, 60, 90, 180} days (6 trials).
Walk-forward: 365d train, 90d test, tiled; selection by train Sharpe.
Same cost model as all studies (10 bps fee, 1 bp half-spread, impact).

## Expected failure modes

Choppy ranges; V-reversals; the 2022-2026 window contains only ~3 OOS
years — statistical power is limited and the verdict may be INCONCLUSIVE
rather than clean either way.

## Pre-registered verdict standard

Same as hypothesis 01: broad B&H outperformance (risk-adjusted) across
symbols AND deflated Sharpe probability > 0.95 (n_trials=6) AND stable
parameter selection. Cumulative trial accounting: this is spec #2 tested
on this dataset.

## Results (2026-07-11, ~3y stitched OOS per symbol, costs included)

- **6/8 symbols beat buy-and-hold on Sharpe** (all but BTC, BNB — the two
  strongest B&H performers). Standouts: XRP (Sharpe 1.04 vs 0.71, DSR
  0.908), SOL (0.99 vs 0.93, DSR 0.875).
- Median DSR 0.624 — below the 0.95 bar. Lookback selection still
  unstable window to window.
- Fixed-lookback robustness (scripts/phase3_verdict.py): median OOS
  Sharpe positive at EVERY L in the grid (0.35-0.74, peak L=14) — broad
  positivity, unlike the hourly spec's noise. Drawdowns roughly halved
  vs B&H on most symbols.
- **Equal-weight 8-symbol portfolio** of the walk-forward OOS curves
  (+1 declared trial): Sharpe 0.87, +108% over ~3y, MDD -44%,
  DSR 0.872 (grid trials) / **0.828 counting all 23 Phase 3 trials**.

Verdict: fails the pre-registered validation bar (DSR < 0.95), so NOT a
confirmed edge — but it is broadly positive across symbols and lookbacks,
diversifies well, and is the only family worth carrying forward. Promoted
to Phase 4 as THE candidate, explicitly labeled unvalidated. The main
statistical limitation is ~3 years of OOS; extending history (Binance 1d
data reaches 2017) is the cheapest way to sharpen the verdict.
