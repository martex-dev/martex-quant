# Hypothesis 08 — Funding-Rate Extremes as a Contrarian Signal

Status: UNDER TEST (pre-registered before results; this file is committed
before scripts/h08_funding_killtest.py runs).

## Hypothesis and rationale

Perpetual funding is the price of crowded positioning: extremely positive
funding means longs are paying heavily to stay levered long — a crowded,
fragile trade whose forced unwind (liquidations, deleveraging) creates
selling pressure. Symmetrically, extremely negative funding marks crowded
shorts. Prediction: **extreme funding predicts forward SPOT returns in
the contrarian direction** (high funding -> weaker forward returns; low
funding -> stronger). Unlike carry (hypothesis 05, needs two legs), a
funding-based directional signal is usable in the single-venue CFD prop
vehicle.

## Specification (kill test — information only, no strategy)

- Data: Binance USDT-perp funding history, full available depth (from
  each contract's launch), 8-symbol universe; daily funding = sum of the
  UTC day's 8h rates; joined to SPOT daily closes from the lake.
- Signal state per symbol-day: trailing-90d percentile rank of daily
  funding. HIGH = >= 90th pct, LOW = <= 10th pct, MID otherwise.
  Window and thresholds are FIXED, not tuned.
- Primary metric: pooled panel E[fwd 7d return | LOW] - E[fwd 7d | HIGH].
- PASS bar (both required):
  1. difference > 0 with 95% moving-block bootstrap CI excluding zero
     (30-day date blocks, cross-section kept intact within blocks);
  2. per-symbol difference positive for >= 5 of 8 symbols.
- Descriptive only (reported, no verdict weight): 1d and 30d horizons,
  and MID-bucket means as sanity baseline.
- Trial ledger: +3 (7d primary, 1d, 30d) -> program total 44.

## Expected failure modes (stated before results)

- Funding extremes coincide with strong trends; the contrarian fade
  fights momentum — the signal may be early, i.e. wrong for days.
- Regime drift: 2020-21 funding levels dwarf 2024-26 levels; trailing
  percentile normalization is the mitigation, but the anomaly may have
  been arbed away as basis desks industrialized post-2022.
- Only ~5-7 years of funding history exists at all; extreme buckets are
  ~10% of days — effective sample is small and crash-clustered.

## Verdict

(filled after the run; FAIL -> the idea is dropped, ledger keeps the
trials; PASS -> proceed to a strategy-grade hypothesis with costs and
walk-forward before anything else)
