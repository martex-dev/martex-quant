# Hypotheses 33-40 — Time-Series & Structure Batch

Status: **COMPLETE (2026-07-12) — 2 signals (H33, H40), 6 kills.**
Trial ledger: +8 -> 100 (with 24-32 batch; before conditional
follow-ups). FU-B1 FIRED (H33 blend). H40's signal graduates via a NEW
pre-registration (docs/hypotheses/42-stop-overlay.md) since no H40
follow-up was registered here. Verdicts at the bottom.

Shared machinery: WIDE 40-coin daily panel unless stated; 95%
moving-block bootstrap (30d blocks, 5,000 draws); features use data
<= t only; info-level tests are gross of costs (costs enter at
strategy grade). Two-sided hypotheses record direction.

## H33 — Multi-horizon momentum blend (+1 trial)

Score s = [r30>0] + [r90>0] + [r180>0] per symbol-day. H16's follow-up
showed the walk-forward SELECTOR chases noise; the institutional fix
(AQR-style) is AVERAGING horizons, never tested here. Claim:
E[fwd7 | s=3] - E[fwd7 | s in {1,2}] > 0 (CI > 0). Monotonicity across
s reported descriptively.

## H34 — Basis momentum (+1 trial, incremental frame)

Legacy 8 + perp cache (data/perp). basis = perp_close/spot_close - 1;
d_basis7 = basis - basis 7d ago. H10 established the basis LEVEL is a
continuation signal (not tested incrementally); H23b killed
funding-LEVEL-as-confirmation. This tests the CHANGE: among
momentum-long symbol-days (r90 > 0), rising basis (d_basis7 > 0) minus
falling basis, fwd 7d. Claim: CI > 0. Family-redundancy risk with H23b
acknowledged up front.

## H35 — Pairs / ratio stat-arb (+1 trial, two-sided)

Legacy 8, all 28 pairs. z = (log(A/B) - mean90) / std90 of the log
price ratio. Signed forward: for |z| >= 1.5, signed_fwd =
-sign(z) * (ratio fwd 7d return). Reversion claim: E[signed_fwd] > 0.
Continuation world predicts the opposite (ratio momentum). Two-sided;
mean_ci over event days. First market-neutral hypothesis in the ledger.

## H36 — Short-leg viability (+1 trial, two-sided)

Wide panel, days with >= 10 rankable coins: bottom-2 by r90, E[fwd7]
minus all-days baseline. Short claim: CI < 0 (weakness continues hard
enough to short). No deployed strategy shorts; CFDs allow it. A pass
here is necessary-not-sufficient: the follow-up applies a doubled
per-side cost on the short leg (swap/borrow unknowns).

## H37 — Breadth dial (+1 trial, two-sided)

Breadth = share of rankable coins with r90 > 0 that day. Test: fwd 7d
of the top-2 momentum picks, top breadth tercile minus bottom tercile.
Meta-finding 2 (sizing beats switching) demands this be a continuous
DIAL if it graduates, never an on/off switch. Tercile monotonicity
reported.

## H38 — Dispersion dial (+1 trial, two-sided)

Dispersion = cross-sectional std of r30 across rankable coins that day.
Test: top2-minus-bot2 fwd 7d spread, high-dispersion tercile minus low.
Rotation earns a spread; more dispersion should mean more spread if the
dial is real.

## H39 — Pick-correlation diversification (+1 trial, two-sided)

For each day's top-2 momentum picks: pairwise correlation of their
daily returns over the trailing 90d. Mean fwd 7d of the pair, low-corr
days (<= median) minus high-corr days. Motivates cluster-diversified
rotation only if picking correlated pairs measurably costs return
(risk effects reported descriptively).

## H40 — Trailing stop, tested honestly (+1 trial, two-sided)

The retail classic. Among uptrend symbol-days (r90 > 0): "stop fired"
days = close has fallen >= 2 x ATR14 from the trailing 30d close-high.
E[fwd30 | stop fired] minus uptrend baseline E[fwd30]. CI < 0 means
stops exit ahead of further weakness (they help); CI >= 0 / noise means
stops sell recoveries (they hurt or do nothing). Meta-finding 2
predicts death; the data referees.

## Conditional follow-ups (pre-registered, +1 trial each if fired)

- FU-B1 (from H33): blend passes -> strategy-grade V1 variant on the
  8 majors: fixed blend signal (equal-weight sign of {30,90,180})
  replacing walk-forward L selection, vol-target sizing unchanged.
  Bars: OOS Sharpe > V1's on the identical protocol AND prop pass
  @1.5x > 50.0%.
- FU-B2 (from H36): short claim passes -> strategy-grade long-short
  wide rotation (long top-2, short bottom-2, same vol budget, doubled
  short-leg costs). Bars: OOS Sharpe > 1.10 AND prop pass @0.5x
  > 62.9%.
- FU-B3 (from H37/H38): a dial passes -> wide rotation with gross
  exposure scaled continuously by the SINGLE BEST dial. Bars: beat
  champion on OOS Sharpe AND prop pass @0.5x.
- FU-B4 (from H35): reversion passes -> pairs sleeve strategy-grade
  (event-driven, both legs costed). Bars: net OOS Sharpe > 0.5 AND
  timestamp-joined corr vs rotation OOS < 0.30 (diversifier bar, per
  the H12 lesson). Own-capital shape (needs shorting both ways) —
  even a pass is post-eval infra, like carry.

## Verdicts (2026-07-12, 64,484 symbol-days; scripts/h33_40_killtests.py)

- **H33 blend: SIGNAL.** E[fwd7] is monotone in the horizon-agreement
  score (0: +0.07%, 1: +0.39%, 2: +0.82%, 3: +3.00%); score-3 minus
  score-1/2 = +2.41% CI [+0.43, +4.39]. Horizon agreement carries real
  information beyond a single lookback. **FU-B1 FIRES**: strategy-grade
  blend-V1 (+1 trial).
- H34 basis momentum | momentum-long: -0.41% CI [-1.46, +0.55] —
  KILLED. Like funding (23b), derivative-positioning changes add
  nothing once price momentum is known. Family closed.
- H35 pairs reversion: -0.64% CI [-1.39, +0.05] — KILLED as
  registered (two-sided, no side excludes 0). Note the sign: the
  near-miss is on the MOMENTUM side — even relative-value ratios trend
  rather than revert here. Recorded as the 6th continuation
  confirmation (descriptive). FU-B4 does not fire.
- H36 short-leg: -0.15% CI [-1.06, +1.00] — KILLED. The bottom of the
  ranking does NOT keep falling: the short leg has no premium to
  harvest net of nothing, let alone costs. Long/flat stands. FU-B2
  does not fire.
- H37 breadth dial: terciles monotone (+0.90% / +1.15% / +2.92%) but
  top-vs-bottom +2.02% CI [-2.10, +5.74] — KILLED (suggestive shape,
  no significance; stays closed per the near-miss rule). FU-B3 no.
- H38 dispersion dial: monotone (+0.50/+1.05/+1.40%) but +0.90%
  CI [-2.66, +3.69] — KILLED. FU-B3 does not fire.
- H39 pick-correlation: -0.18% CI [-3.19, +2.18] — KILLED. Forcing
  diversified picks buys no return (risk effects were not the claim).
- **H40 trailing stop: SIGNAL, stops-help direction.** Within uptrends
  (r90>0), after price falls >= 2xATR14 off its 30d high, fwd30 is
  -8.77% WORSE than uptrend baseline, CI [-15.57, -2.17]. The one
  switch-like idea that survived an info test — but it had NO
  registered follow-up here, so graduation requires a new spec:
  pre-registered as docs/hypotheses/42-stop-overlay.md with
  incremental bars vs the deployed systems.

## FU-B1 verdict (2026-07-12, scripts/h41_h42_fub1_studies.py, +1 trial)

**KILLED.** On the 1,710d common window (shortened by the blend's 181d
warmup + inner join): blend-V1 Sharpe 0.60 vs V1 0.53 (bar1 PASS, MDD
also better: -22.0% vs -25.1%), but prop pass @1.5x 28.0% vs the
registered >50.0% bar — FAIL. Honest note: V1 itself shows only 27.9%
on this same shortened window (the 50% figure came from the longer
phase-5 window), so the blend merely MATCHED the deployed engine's
pass rate while beating its Sharpe. Blend DSR 0.857. The averaging idea
is directionally right but not strong enough to displace anything;
closed per the near-miss rule.
