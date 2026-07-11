# Hypothesis 08 — Funding-Rate Extremes as a Contrarian Signal

Status: **FAILED the kill test (2026-07-11)** — and the point estimates
lean AGAINST the contrarian story. See Verdict.

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

## Verdict (2026-07-11, 17,910 symbol-days, 2019-12 .. 2026-07)

FAIL on both pre-registered criteria: 7d LOW-minus-HIGH = -0.95%
(CI [-3.20%, +1.39%] — straddles zero, wrong sign), sign consistency
4/8 (needed 5).

The interesting part: every point estimate leans the WRONG way for the
contrarian narrative. Days with HIGH funding (crowded longs) were
followed by HIGHER returns — +3.30% vs +2.35% at 7d, and +12.61% vs
+4.83% at 30d. "Everyone is overleveraged long, the market must
correct" is, on average, backwards: extreme positive funding is a
feature of bull trends that keep going. This is consistent with our
core momentum findings — crowdedness accompanies trends; fading it
fights the one effect we know is real.

A momentum-flavored funding signal (HIGH funding as confirmation)
would be a NEW hypothesis — noting for the ledger that its 30d point
estimate (+7.78%) also failed to clear zero (CI [-0.77%, +17.58%]),
so it is NOT promoted either. Idea closed. Funding data (7y, cached
in data/funding/) remains for the carry project (hypothesis 05).
