# Hypothesis 43 — Combination Batch on the Rotation-Stop Base

Status: **PRE-REGISTERED (2026-07-12)** — no test has run yet.
Trial ledger: +1 to +3 conditional -> up to 107.

## Motivation (user request, filtered by the H12 lesson)

Requested combinations: rotation-stop paired with vol-target,
crash-bounce, plain rotation, and triples. The H12 lesson stands:
blending books with correlated returns AVERAGES them and insures
nothing (V1 x rotation true corr 0.77 killed the original combined
book). H41 found the first genuinely low-corr component: the
crash-bounce overlay (corr 0.188 to rotation). So this batch screens
FIRST, then trials only what the screen admits.

## Correlation screen (descriptive, NOT trials)

Timestamp-joined daily-return correlations on each pair's common OOS
window, from the cached validation streams:
(a) rotation-stop x vol-target-V1, (b) rotation-stop x champion
rotation, (c) rotation-stop x crash-bounce overlay (overlay built on
rotation-stop's own idle cash, H41 construction), (d) V1 x that
overlay. **Admission rule: a blend trial runs only if every component
pair in it has corr < 0.30.**

Pre-declared expectations: (b) will be ~0.9 — rotation-stop IS rotation
plus an exit rule; blending a strategy with its own parent is the same
book twice. NO trial is registered for rotation-stop + rotation at any
screen outcome (a tautology is not worth a ledger slot). (a) is
expected ~0.5-0.8 (both are long-crypto momentum); if it screens in,
the trial below runs honestly.

## Registered conditional trials

- **43a — rotation-stop + crash-bounce overlay** (+1 trial; runs if
  screen (c) < 0.30): on trigger days (BTC day < -3%) the account's
  idle cash (1 - rotation-stop gross, floor 0) goes EW into alts for
  one day at H22 costs (0.22% RT). Bars vs rotation-stop ALONE on the
  same window: (1) Sharpe higher, (2) prop pass @0.5x (real firm
  1-step static, 20k paths) higher, (3) MDD no worse than 5 points.
  Note H41 failed bar 2 on the plain-rotation base (45.3% vs 62.8%);
  the stop base has far lower MDD (-29% vs -58%), so the bounce
  variance lands on a calmer book — genuinely uncertain, hence the
  trial.
- **43b — 50/50 rotation-stop + V1** (+1 trial; runs only if screen
  (a) < 0.30): daily 50/50 return blend. Bars: Sharpe > best sleeve's
  AND prop pass @0.5x > rotation-stop's, MDD rule as above.
- **43c — triple: 50/50 V1 + (rotation-stop with bounce overlay)**
  (+1 trial; runs only if screens (a), (c), (d) ALL < 0.30). Bars as
  43b, compared against the best component book in the same run.

## Disposition rules

A passer becomes eligible for its own paper account (one spec per
record). A screened-out pair is recorded with its measured correlation
and closed WITHOUT consuming a trial. A failed trial closes per the
near-miss rule. Nothing here touches the eval runbook before the gate.
