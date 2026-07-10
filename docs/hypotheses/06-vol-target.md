# Hypothesis 06 — Volatility-Targeted Momentum (Daily)

Status: **SURVIVES ITS RELATIVE STANDARD** (2026-07-11) — better Sharpe,
half the drawdown, and the best prop pass rate vs hypothesis 02; absolute
edge still unvalidated (portfolio DSR 0.660 < 0.95).

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

## Results (2026-07-11, extended 2017+ data)

Per symbol (own full history, 6-trial DSR): 5/8 beat B&H on Sharpe,
median DSR 0.898; drawdowns compressed to -33%..-57% vs TSMOM's
-55%..-92% (DOGE: Sharpe 1.02, MDD -33%, DSR 0.976).

Equal-weight portfolio, common 4.7y OOS window (includes 2022 bear),
DSR benchmarked against ALL 38 project trials:
- Sharpe 0.74 (best of the three finalists), **MDD -20.0%** (vs -39%
  unsized), CAGR +6.7%, DSR 0.660
- Prop-sim best: GENERIC-A @ 1.0x -> **38.4% pass** (best of all
  families), median 55 days, EV +$1,751 per attempt, EV/day +$31.8

Verdict vs its pre-registered relative standard (better Sharpe AND
materially lower MDD AND better prop pass rate than hyp 02): **all
three met**. Absolute validation (DSR > 0.95): not met. Role: the
funded-stage / capital-preservation configuration.
