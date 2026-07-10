# Hypothesis 06 — Volatility-Targeted Momentum (Daily)

Status: UNDER TEST (pre-registered before results).

## Hypothesis and rationale

Hypothesis 02's momentum signal is real-ish but its constant-notional
sizing produces -44% drawdowns — crypto vol swings 3-5x between regimes,
so constant notional means wildly inconsistent risk. Sizing positions to a
constant RISK budget (target_vol / realized_vol, capped at 1x) should cut
drawdown roughly proportionally to the vol overshoot while keeping most
return, raising Sharpe and — critically for prop-fit — compressing the
left tail that trips trailing-drawdown rules. This is the standard
institutional implementation of TSMOM (Moskowitz et al. sized this way).

## Specification

Daily bars, signal = hypothesis 02's L-day momentum (grid L ∈
{7,14,30,60,90,180}, 6 trials). Exposure = min(1, 0.30 / realized_vol_30d)
when signal on, else 0. Target vol (30% ann.) and vol window (30d) FIXED.
Long/flat, no leverage (cap 1x). Walk-forward: 365d train, 90d test.

## Expected failure modes

Vol spikes lag entries (sizing down after the damage); quantized rebalance
churn adds costs; in steady low-vol trends it is identical to hyp 02.

## Pre-registered verdict standard

vs hypothesis 02 on the same OOS spans: comparable or better Sharpe AND
materially lower max drawdown AND better prop-sim pass rate. DSR > 0.95
(n_trials=6) against B&H for validation. Trial accounting: specs #06.

## Results

(filled by scripts/phase3_studies.py --study vol-target)
