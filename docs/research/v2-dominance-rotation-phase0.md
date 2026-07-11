# V2 Phase 0 — Bitcoin Dominance Rotation (Dual Momentum)

Status: **V2-H1 FAILED THE KILL TEST (2026-07-11) — PROJECT CONCLUDED
AT M1.** See results at the bottom. Trial ledger after this study: 41.

## 1. Feasibility & what this actually is

Decoded, the four-quadrant system is:

|  | Dominance rising | Dominance falling |
|---|---|---|
| **Market uptrend** | long BTC | long alts |
| **Market downtrend** | short alts | short BTC |

i.e. LONG the relatively strong leg in uptrends, SHORT the relatively
weak leg in downtrends. This is **dual momentum** (Antonacci): absolute
(time-series) momentum sets direction, cross-sectional (relative)
momentum picks the asset. Both components are documented anomalies with
real literatures; crypto cross-sectional momentum has mixed-positive
academic evidence. The idea deserves a test. That is NOT the same as
the video's specific parameters deserving belief.

Corroborating our own evidence: V1 found crypto time-series momentum
survives on daily bars (portfolio DSR 0.821-0.911 territory) and that
hourly momentum died after ~2021 — which matches the trader's own story
of abandoning his 2h system after 2022. His "downgrade to 12h/6h" is
consistent with the edge decaying at high frequency. His pre-2022
high-leverage success is unverifiable single-survivor evidence and gets
zero weight.

## 2. Brutally honest weaknesses (pre-registered skepticism)

1. **BTC.D is a bad variable.** TradingView's dominance = BTC cap /
   total crypto cap, where the denominator includes stablecoins and
   thousands of illiquid coins. Stablecoin growth mechanically depresses
   dominance with zero alt strength; dead coins pollute it; its history
   is vendor-dependent and not reproducible. DECISION: define dominance
   as a ratio of INVESTABLE indices we build ourselves from the lake:
   D_t = BTC price index / equal-weight alt index. Same economic
   content, clean provenance, reproducible. The external BTC.D may be
   compared once, out of curiosity, never as the signal.
2. **Survivorship bias, and it cuts asymmetrically.** Our alt universe
   is today's survivors. That INFLATES the long-alts quadrant (dead
   coins never rallied) and DEFLATES the short-alts quadrant (the best
   shorts were the coins that died). Mitigation: name it, bound it,
   widen the universe with listing-date awareness; a positive verdict
   that depends on the long-alts quadrant gets an automatic haircut.
3. **Researcher degrees of freedom explode here.** Trend definition x
   dominance lookback x timeframe x universe x short rules — this is
   how video strategies are born. Mitigation: tiny pre-registered
   grids, every cell counted in the global trial ledger, DSR bars
   against ALL trials ever run in this program.
4. **Shorts are not free.** Short exposure at a CFD/perp venue pays
   funding/swap; our V1 engine models no borrow costs (known Phase 2
   limitation). The 4y funding history we pulled for hypothesis 05
   says crypto funding averages 6-8%/yr AGAINST shorts on majors.
   Bear-quadrant results without funding costs are fiction; the cost
   model must be extended before any short backtest is believed.
5. **Regime-switching costs.** Four quadrants means rotation churn at
   boundaries; whipsaw in chop is the classic failure mode of regime
   systems. Turnover must be reported per hypothesis.
6. **12h long / 6h short asymmetry** is a plausible story (crypto bear
   moves are faster than bull moves — vol asymmetry is real) and also
   exactly the kind of detail people fit to their own trade history.
   Tested as its own hypothesis against symmetric baselines, on
   resampled bars from our validated 1h lake.

## 3. Mathematical formulation

- Alt index: A_t = equal-weight chained index of the alt basket
  (rebalanced daily; basket membership fixed per study, listing-aware).
- Market index: M_t = equal-weight index of BTC + basket.
- Dominance proxy: D_t = P_BTC,t / A_t.
- Trend state: T_t = sign(M_t / M_{t-Lm} - 1), Lm in a <=3-value grid.
- Dominance state: R_t = sign(D_t / D_{t-Ld} - 1), Ld in a <=3-value grid.
- Target book: quadrant map above; sizing via the V1 vol-target rule
  (30% ann. target, capped), because V1 proved sizing beats switching.
- Costs: V1 model + funding on shorts (from pulled funding history).

## 4. Data requirements

Already in the lake: 8 symbols, 1h + 1d, 2017+, validated. New needs:
(a) resampler 1h -> 6h/12h (pipeline addition, no vendor); (b) wider
alt universe (top-liquidity, listing dates recorded) to de-concentrate
the basket; (c) funding-rate history as a first-class dataset (fetcher
exists from hypothesis 05). No new vendors required. NOT needed:
TradingView BTC.D (see 2.1).

## 5. Research hypotheses (pre-registered, verdicts before results)

- **V2-H1 (KILL TEST, cheapest first):** does dominance-proxy direction
  predict subsequent BTC-minus-alts relative return? Information test
  only — rank correlation / conditional means with block-bootstrap CIs
  across Ld grid, daily bars, 2017+. PASS bar: significant positive
  predictiveness robust across at least 2 of 3 lookbacks in the
  direction the quadrant logic requires. FAIL -> project ends at M1.
- **V2-H2:** full 4-quadrant rotation, daily bars, long+short with
  funding costs, walk-forward, vs benchmarks (V1 candidate, BTC B&H,
  long-only rotation). Bars: beats the V1 candidate risk-adjusted AND
  clears DSR > 0.95 against the cumulative trial ledger for validation;
  anything less is at best a labeled candidate.
- **V2-H3:** timeframe study — daily vs 12h vs 12h/6h asymmetric, same
  logic, resampled bars. Bar: material improvement over daily, stable
  across symbols; else asymmetry is rejected as decoration.

## 6. Architecture (the V1 platform grows; no second codebase)

Same repo, same standards. The genuinely new engineering:
1. **Multi-asset engine loop** — V1's engine is single-instrument by
   MVP decision; rotation is inherently a portfolio decision each bar.
   Extension: multi-symbol bars, one portfolio, per-symbol fills.
2. **Configurable signal stack** (the requested improvement): pipeline
   of composable, swappable components — RegimeSignal (trend def),
   RelativeStrengthSignal (dominance def), Allocator (quadrant map),
   Sizer (vol target), each a small interface; a strategy is then a
   CONFIG, not a class. V1 strategies get re-expressed in it later.
3. **Resampler** with strict bar-alignment validation (6h/12h from 1h).
4. **Funding-cost model** on short positions in the simulated broker.
Reused untouched: data lake, validator, metrics/DSR, walk-forward,
prop_sim, risk policies, dashboard (gets a V2 research tab later).

## 7. Roadmap & first milestone

- **M1 (first): data + kill test.** Resampler, indices, dominance
  series, V2-H1 information study. Exit: verdict on V2-H1. If FAIL:
  write it up, stop, V2 concludes honestly at near-zero cost.
- M2: multi-asset engine + signal stack + funding costs (+tests incl.
  look-ahead impossibility for the multi-asset path).
- M3: V2-H2/H3 walk-forward studies, verdicts.
- M4: prop-fit simulation; combined V1+V2 book analysis (the real
  prize: V2's short book is active exactly when V1 sits flat).

## 8. Relationship to V1 operations

V1 paper shakedown and eval schedule are UNTOUCHED by this project.
V2 is a research workstream; nothing from it ships to live trading
until it clears the same gates V1 cleared, plus multi-asset paper
trading of its own.

## M1 RESULTS (2026-07-11, scripts/v2_m1_killtest.py, 3,249 days 2017-2026)

Pre-registered bar: dominance-direction predicts next-30d BTC-minus-alt
relative return, 95% block-bootstrap CI > 0 on >= 2 of 3 lookbacks.

| Ld | E[rel | dom rising] | E[rel | dom falling] | diff | 95% CI | verdict |
|---|---|---|---|---|---|
| 14d | -2.09% | -5.13% | +3.04% | [-2.97%, +10.82%] | fail |
| 30d | -3.21% | -4.02% | +0.81% | [-5.22%, +6.06%] | fail |
| 60d | -3.14% | -5.22% | +2.08% | [-5.45%, +10.81%] | fail |

**0/3. V2-H1 FAILS.** Point estimates are mildly positive but drowned in
noise — the dominance signal is statistically indistinguishable from zero.

Worse for the strategy than the headline: the descriptive quadrant table
CONTRADICTS its core logic. In uptrends with RISING dominance (the
"long BTC, ignore alts" quadrant), alts still outperformed BTC forward
(+18.3% vs +9.9%). In downtrends with rising dominance (the "short
alts" quadrant), alts averaged +5.0% forward — the short loses on
average. The survivor-alt basket outperformed BTC in ALL four quadrants,
which is partly the pre-registered survivorship caveat showing up in the
data, and partly the point: even leaning WITH that bias, the dominance
variable adds nothing significant.

What survives: the trend split itself (uptrend quadrants far outperform
downtrend quadrants) — which is V1's already-validated momentum edge,
nothing new.

Disposition: per pre-registration, V2 ends here. No strategy code was
written. Reopening dominance rotation requires a NEW pre-registered spec
with a materially different construction (e.g. cap-weighted investable
index, broader listing-aware universe) and a stated reason to believe it
differs — and it inherits the 41-trial ledger. The M1 infrastructure
(resampler, indices) is general-purpose and stays.
