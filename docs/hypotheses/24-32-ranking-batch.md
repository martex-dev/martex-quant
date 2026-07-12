# Hypotheses 24-32 — Cross-Sectional Ranking Batch

Status: **COMPLETE (2026-07-12) — ALL 9 KILLED.** Trial ledger: +9 -> 92.
FU-A did NOT fire (no passer). Verdicts at the bottom.

Motivation: the only absolutely validated spec (rotation, DSR 0.990)
is a cross-sectional ranking, and meta-finding 3 says these edges feed
on breadth. The institutional factor literature offers ranking
alternatives never tested here. Each is tested at info level first
(kill-test rule); none touches a strategy build unless it passes AND
beats the deployed ranking's reference spread.

Shared protocol (identical to H16): WIDE 40-coin universe, daily lake
data, days with >= 10 rankable coins. Rank all coins by the feature at
close of day t (features use data <= t only), take mean fwd 7d return
of top-2 minus bottom-2 ("spread"). 95% moving-block bootstrap on
daily spreads (30d blocks, 5,000 draws). References (NOT trials):
r30-ranking and r90-ranking spreads computed identically on the same
panel — the deployed family's information.

PASS bar per hypothesis: spread CI excludes 0 in the claimed direction
(two-sided hypotheses: either side, direction recorded).

## H24 — Risk-adjusted momentum (+1 trial)

Rank by r90 / vol90 (vol90 = std of daily returns over the same 90d).
Institutional standard (Sharpe-momentum). Claim: spread CI > 0.

## H25 — 52-week-high proximity (+1 trial)

Rank by close / rolling-365d-max-close (George & Hwang 2004). Related
to H18 (overextension = strength) but a distinct, anchoring-based
measure. Claim: spread CI > 0.

## H26 — Residual momentum (+1 trial)

Strip BTC beta: daily residual e_t = r_t - beta * r_btc_t, beta from
trailing 90d cov/var (data <= t). Rank by sum of residuals over 90d.
BTC excluded from ranking. (Blitz et al. — momentum net of the market
factor is cleaner.) Claim: spread CI > 0.

## H27 — Low-volatility anomaly (+1 trial, two-sided)

Rank by vol90 ascending (top-2 = calmest coins). Equity literature says
low-vol wins; crypto continuation world may say the opposite. Spread =
low-vol top-2 minus high-vol bottom-2, fwd 7d. CI excludes 0 either
side = SIGNAL, direction recorded.

## H28 — MAX / lottery effect (+1 trial, two-sided)

Rank by max single-day return in trailing 30d. Lottery claim (Bali et
al.): low-MAX minus high-MAX spread > 0. H13 (shocks continue) predicts
the opposite. Two-sided; the data referees.

## H29 — Illiquidity premium (+1 trial, two-sided)

Rank by Amihud measure: mean(|ret| / (close * volume)) over 30d.
Claim: illiquid top-2 minus liquid bottom-2 > 0. Pre-noted caveat: a
positive result is NOT tradable until a cost-feasibility check passes
(illiquid coins cost more to trade); this trial can only graduate to
a follow-up with an explicit cost haircut.

## H30 — Volume-shock ranking (+1 trial, two-sided)

Rank by volume(t) / mean-volume-30d. Distinct from H21 (which
conditioned volume WITHIN momentum picks and died as a filter): here
volume is the primary ranking over the whole cross-section.

## H31 — Trend smoothness / frog-in-the-pan (+1 trial)

Among coins with r90 > 0 that day (>= 6 such coins required): rank by
share of positive days within the 90. Claim (Da-Gurun-Warachka):
smooth top-2 minus jumpy bottom-2 fwd 7d > 0.

## H32 — Skip-week momentum (+1 trial)

Rank by r(90..7) = close[t-7] / close[t-90] - 1 (excludes the most
recent week). Complements H16's finding that the recent week is real
info but noisy inside selectors; equity convention (12-2) skips the
recent month for the same reason. Claim: spread CI > 0.

## Conditional follow-up FU-A (pre-registered, +1 trial if fired)

If ANY of {H24, H25, H26, H31, H32} passes AND its spread point
estimate exceeds BOTH reference spreads (r30, r90) on this panel:
run strategy-grade wide rotation (event-driven, walk-forward L-grid
protocol unchanged) with THE SINGLE BEST such ranking substituted for
raw momentum. Bars: OOS Sharpe > 1.10 AND prop pass @0.5x > 62.9%
(beat the champion on both, same firm rules, 20k paths). One follow-up
maximum from this batch — the best passer only.

## Verdicts (2026-07-12, 64,484 symbol-days; scripts/h24_32_killtests.py)

**All nine KILLED — no ranking alternative passes its info bar.**
References on this panel: r30 spread +0.869% (noise), r90 +0.745%
(noise) — consistent with H16's r30 reference; the champion's edge
lives in the walk-forward strategy layer, not in naive daily spreads.

- H24 risk-adjusted: +0.768% CI [-0.43, +2.23] — noise.
- H25 52w-high: +0.977% CI [-0.35, +2.36] — noise (best point
  estimate of the batch, still inside the CI).
- H26 residual momentum: +1.076% CI [-0.81, +2.17] — noise. Beats
  both references on point estimate but FAILED its own CI bar, so
  FU-A does not fire (pass AND beat references was required).
- H27 low-vol: +0.822% toward HIGH vol CI [-1.07, +2.38] — noise;
  no low-vol anomaly in crypto on this panel, direction if anything
  favors high vol (continuation world).
- H28 MAX/lottery: +0.471% toward high-MAX CI [-1.05, +2.19] — noise;
  the equity lottery effect does not appear here.
- H29 illiquidity: +0.761% CI [-0.62, +2.39] — noise (and would have
  faced a cost haircut anyway).
- H30 volume-shock: +0.305% CI [-1.26, +1.76] — noise.
- H31 smoothness (FIP): -0.142% CI [-2.58, +1.98] — noise, wrong
  side; smooth trends do NOT beat jumpy ones among winners here.
- H32 skip-week: +0.143% CI [-1.21, +1.54] — noise; dropping the
  recent week REMOVES information (coherent with H16: the recent week
  is real info, just poisonous inside selectors).

Meta-note: nine institutional equity-factor rankings, zero survivors —
the deployed raw-momentum ranking is not obviously improvable by any
standard factor on this universe. The edge is the protocol (walk-forward
+ vol targeting + breadth), not the ranking refinement.
