# Research Backlog (living document)

Rules of the program: every hypothesis gets a numbered pre-registered doc
before its test runs; kill test (cheap information study) before any
strategy build; every trial joins the global ledger (currently **44**)
and raises the DSR bar for all; the backlog is PRUNED by prior, not
exhaustively executed — a test that is cheap in hours still costs trials.

Scoring: prior = probability of a real edge given literature + OUR ledger;
cost = hours to verdict; deploy = usable in the current vehicle (CFD prop,
single venue, daily-ish cadence)?

## Already answered — do not re-litigate without new construction

| Idea | Verdict | Where |
|---|---|---|
| Trend persistence / momentum | VALIDATED-ish; deployed | hyp 02/06/07 |
| Volatility clustering | Exploited as sizing (not an "edge" — a fact) | hyp 06 |
| Vol-regime gating | REJECTED | hyp 03 |
| Mean reversion (incl. "adaptive") | REJECTED 0/8 | hyp 04 |
| BTC dominance rotation | KILLED at information stage | V2 |
| Funding extremes (both directions) | KILLED at information stage | hyp 08 |
| Hourly/sub-hourly anything | Costs eat it; REJECTED | hyp 01, 04 |

## Tier A — next in line

1. **Calendar effects** (day-of-week, month-end/quarter-end, the 8h
   funding-window cycle). Rationale: flow-driven periodicity (payrolls,
   rebalancing, funding settlements). Data: IN HAND (1h+1d lake, funding
   cache). Cost: ~half a day, pure kill test. Prior: modest (0.15-0.25 —
   documented in equities, decays fast when known). Overfit risk: HIGH
   (many slices — needs one pre-registered partition, no fishing).
   Deploy: yes (timing overlay on the live system). **Priority 1: the
   cheapest remaining test on data we already own.**
2. **Cross-sectional momentum / relative-strength rotation** (rank the 8,
   hold top-K). Rationale: strongest academic family not yet tested here;
   V1's time-series cousin survived. Data: in hand. Cost: HIGH — needs
   the multi-asset engine (the V2-M2 build that was never triggered),
   ~2-3 sessions. Prior: the best on this list (0.3-0.4). Overfit risk:
   moderate (K and lookback grids — keep tiny). Deploy: yes, could
   directly upgrade the deployed system. Survivorship caveat mandatory.
   **Priority 2: highest expected value, gated on the engine build.**
3. **Spot-vs-perp basis** (premium/discount as state variable). Data:
   perp klines pullable free from Binance futures; joins existing lake.
   Cost: ~1 day incl. data. Prior: 0.15-0.25 (cousin of funding, which
   just died — but basis is a level, funding is a flow; weak separate
   claim). Overfit risk: moderate. Deploy: yes. Priority 3.
4. **Carry infrastructure** (hyp 05 — premium CONFIRMED 5.8-7.9%/yr
   gross). Not a test, a build: two-leg engine + margin modeling. Deploy:
   NO for the prop account (needs two venues/legs) — own-capital project
   after the eval. Priority: post-eval.

## Tier B — parked pending data decisions

- ~~**Options implied vol (Deribit DVOL)**~~: **CLOSED 2026-08-27 by H67
  (KILLED).** Data collected and kept (`data/dvol/`, BTC+ETH, 2021-03-24
  on). The premium is real (BTC +8.72 vol points gross) and dies on cost;
  it is also decaying (−17.59%/yr in 2026). The prior of 0.15 was, for
  once, roughly calibrated. Only BTC and ETH publish DVOL, so no breadth
  remedy exists. Not reopened without a new pre-registration.
- **Term structure (quarterly futures curve)**: pullable; thin history
  pre-2020, contango/backwardation as regime. Prior 0.15.
- **BTC ETF flows**: public data but only since 2024-01 — statistically
  toothless for years yet. Park on sample size.
- **Stablecoin flows / exchange reserves / miner selling**: on-chain data
  provenance is vendor-dependent (Glassnode paid tiers); revisit only
  with a budget decision. Prior unknowable until data is trustworthy.

## Triage of external idea list (2026-07-12)

Already settled by the ledger: cross-sectional rotation (DONE — paper
account live, hyp 11); basis/premium (KILLED, hyp 10); dominance-as-
feature (KILLED, V2 kill test was exactly this); weekend/calendar
(settled, hyp 09); risk-mgmt alpha (half-deployed as vol targeting).

Newly added:
- **Shock persistence** (single-day extreme moves -> next-week returns):
  hyp 13, kill test run 2026-07-12. Distinct horizon from validated
  momentum.
- **Vol-expansion breakout** (compression -> eruption carries direction):
  hyp 14, kill test run 2026-07-12. Distinct from rejected hyp 03.
- **Correlation-spike de-risking** (cut exposure when pairwise
  correlations spike): the untested half of "risk management alpha";
  cheap, conditional overlay on deployed strategies. Prior 0.2.
- **Market breadth**: parked until a WIDE universe exists — with 8 coins
  breadth collapses into the market index momentum we already validated.
  A top-50 listing-aware universe pull unlocks it AND the survivorship
  re-runs (one data project, two payoffs). Queued.
- **Regime clustering / ML feature discovery**: Tier B with guardrails —
  only after the feature set contains more validated inputs; ML as
  researcher not signal, walk-forward-honest, every derived claim
  pre-registered. Not before the wide-universe project.
- **Crowded-trade composite / liquidations**: still blocked on paid OI/
  liquidation data. Unchanged.
- **Stat-arb pairs**: needs shorts + funding cost model in engine;
  own research arc, after carry.

## New candidates added 2026-07-11 (post kill-test round)

- **Cross-sectional short-term reversal**: do last week's top-ranked
  coins underperform NEXT week within the ranking (momentum at 30-90d,
  reversal at 3-7d is the equity pattern)? Data in hand; cheap. Prior
  0.15-0.2.
- **Dispersion / correlation regime**: when pairwise correlations
  collapse, does rotation (hyp 11) earn more? Conditional test AFTER
  the rotation strategy exists. Data in hand.
- **Basis/funding as momentum CONFIRMATION**: hyp 08+10 both showed
  significant wrong-direction (continuation) point estimates. A
  pre-registered incremental test — does adding the positioning state
  improve the DEPLOYED momentum system? — is legitimate; bar: must beat
  price-only momentum, not zero. Prior 0.2.

## Tier C — near-permanent park, with reasons

- **Fear & Greed Index**: mostly a price transform — circular with
  momentum; testing it re-tests momentum with extra steps.
- **Google Trends / social sentiment**: crowded literature, weak
  out-of-sample record, data revisions make honest backtests hard.
- Anything whose definition can absorb any outcome (SMC-style): not
  falsifiable, not science, not here.

## Process note

"Always test the highest-EV hypothesis next" — adopted, with one
amendment: EV includes the LEDGER COST. At 44 trials, each new spec
nudges the noise ceiling for everything, including the deployed system.
The backlog exists to say no cheaply; most of it should die unexecuted.
