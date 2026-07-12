# Hypothesis 43 — Combination Batch on the Rotation-Stop Base

Status: **COMPLETE (2026-07-12)** — screen admitted one blend; it was
killed on the eval bars. Trial ledger: +1 consumed -> 105 (43b/43c
screened out, no trials consumed). Verdicts at the bottom.

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

## Verdicts (2026-07-12, scripts/h43_combo_study.py)

Correlation screen (timestamp-joined, common windows):
- (a) rotation-stop x V1: **+0.521 — SCREENED OUT.** 43b and 43c never
  fire. The H12 lesson now has a second measurement: every long-crypto
  momentum book correlates too highly with every other one to blend.
- (b) rotation-stop x champion rotation: **+0.821** — the pre-declared
  tautology, confirmed. No blend of a strategy with its own parent.
- (c) rotation-stop x crash-bounce overlay: **+0.118 — ADMITTED.**
- (d) V1 x overlay: +0.141 (moot, since (a) failed).

**43a — KILLED on the eval bars** (2,880d window, 317 bounce days,
mean 82% idle cash deployed): Sharpe 1.55 vs 1.47 (bar 1 PASS), CAGR
+79.0%/yr vs +42.9%, DSR 1.000 — but prop pass @0.5x **47.5% vs 73.0%**
(bar 2 FAIL) and MDD -37.6% vs -29.0% (bar 3 FAIL, worse by 8.6 pts).
Identical failure geometry to H41: the bounce deploys idle cash into
the highest-variance days on the calendar and the firm's 3% daily rule
punishes exactly that. NO paper account — a paper record of a book the
eval can't use would measure execution of nothing actionable.

Disposition: rotation-stop + bounce replaces H41's book as THE
own-capital archive candidate (higher Sharpe, higher CAGR, smaller
MDD than H41's version). Own-capital bars (not eval-shaped) to be
registered post-funded, per the backlog.
