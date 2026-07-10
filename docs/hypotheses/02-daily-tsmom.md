# Hypothesis 02 — Time-Series Momentum, Daily Bars

Status: UNDER TEST (pre-registered before results).

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

## Results

(filled by scripts/phase3_studies.py --study daily-tsmom)
