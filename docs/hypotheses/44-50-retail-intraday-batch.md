# Hypotheses 44-50 — Retail Intraday Batch (Maker-Fee Regime)

Status: **COMPLETE (2026-07-12) — all 7 retail claims killed; H44/H45
significantly INVERTED.** Trial ledger: +7 -> 112. The registered
follow-up did not fire (no passers); the inversions graduate via a new
pre-registration (docs/hypotheses/51-intraday-fade.md). Verdicts at
the bottom.

## Stated reason for reopening the frequency family (per process)

Meta-finding 6 ("frequency kills") was established under a TAKER cost
model (~0.22% round trip). The live venue is now Bybit USDT perps,
where MAKER fees are 0.01-0.02%/side — a 5-20x cheaper toll. The kill
verdicts said "intraday signal cannot outrun taker costs", not "no
intraday signal exists". This batch tests the mechanical cores of
popular retail day-trading styles (ORB, session momentum, key levels,
funding windows) at info level on 15m data; any survivor faces a
strategy-grade test under an HONEST maker-fill model (limit fills only
when the next bar trades through the price; unfilled = missed trade).

Data: Bybit USDT perp 15m OHLCV, 12 liquid majors, max history
(scripts/pull_intraday.py -> data/intraday/). Funding cache reused for
H47. Shared machinery: 95% moving-block bootstrap (30d day-blocks).
Info tests are gross; the maker toll line is printed next to every
effect size for context (effect must plausibly clear ~4bp/trade).

## The seven (each +1 trial; two-sided where the continuation
## meta-finding argues against the retail folk-claim)

- **H44 Opening-range breakout (ORB)**: day = 00:00 UTC. Range = first
  hour's high/low. Claim: a 15m close beyond the range in the first
  6h predicts continuation to the day close (signed fwd). CI > 0.
- **H45 First-hour momentum**: 00:00-01:00 UTC return sign predicts
  the 01:00->24:00 remainder. CI > 0.
- **H46 US-open session momentum**: 13:30-16:00 UTC return predicts
  16:00->24:00 (H20 found US hours carry the daily drift; this is the
  tradable version). CI > 0.
- **H47 Funding-window drift**: around funding stamps (00/08/16 UTC),
  conditioned on current funding sign (8 majors, funding cache):
  E[return 30m after | funding>90th pctile] vs baseline. Two-sided.
- **H48 Previous-day high/low break**: first crossing of yesterday's
  high before 12:00 UTC -> continuation to day close (and mirror for
  low). CI > 0 pooled signed.
- **H49 Vol-burst continuation**: |15m ret| > 4x rolling 1d std ->
  next 2h signed continuation. Two-sided (burst reversion is the folk
  counter-claim).
- **H50 VWAP stretch**: distance from session-anchored VWAP > 2x its
  daily std -> next 2h. Two-sided (retail claims reversion; the
  continuation meta-finding predicts the opposite).

## Strategy-grade follow-up (pre-registered, max TWO fired)

The two strongest passers (by CI-lower-bound / toll ratio) get
event-driven builds with the maker-fill model (fee 0.02%/side, fill
only if next bar's range crosses the limit; market exits at taker
0.055%). Bars: net Sharpe > 1.10 (champion) on the common window OR
timestamp-joined corr < 0.30 vs rotation-stop AND net Sharpe > 0.7
(diversifier bar). Prop-sim at sprint and sustainable scales reported.
Survivors join the live book only via the runbook (funded stage or a
subsequent eval) — never mid-attempt.

## What this batch does NOT do

No discretionary/unfalsifiable claims (ICT "liquidity" narratives,
order-flow reads without order-flow data). No taker-cost re-tests.
No deployment before validation, regardless of sprint calendar.

## Verdicts (2026-07-12, ~2M 15m bars, 12 Bybit perps 2021+;
## scripts/h44_50_killtests.py; maker toll ~0.04% RT for context)

- **H44 ORB: KILLED as claimed — SIGNIFICANTLY INVERTED.** Breakout
  events are followed by REVERSAL to the day close: -0.1625% per
  event, CI [-0.29%, -0.04%], n=19,739. The fade is ~4x the toll.
- **H45 first-hour momentum: KILLED as claimed — SIGNIFICANTLY
  INVERTED.** -0.2010%, CI [-0.34%, -0.05%], n=21,111. Fade ~5x toll.
- H46 US-open session momentum: +0.035%, CI includes 0 — KILLED.
  (H20's US-hours drift is real at the daily level but not tradable
  as an intraday session signal.)
- H47 funding-window drift: +0.040%, CI [-0.00%, +0.09%] — KILLED
  (near-miss on the continuation side; stays closed).
- H48 previous-day levels: -0.087%, CI includes 0 — KILLED (leaning
  inverted, not significant).
- H49 vol-burst: -0.007%, dead center — KILLED.
- H50 VWAP stretch: +0.011%, CI includes 0 — KILLED both directions.

Meta: **crypto CONTINUES at daily+ horizons and REVERTS intraday.**
Every popular breakout-style retail entry tested is, at best, noise —
and at the two most popular trigger points it is significantly the
WRONG side of the trade. Not a contradiction of H04 (1h Bollinger
strategy, taker costs, spot): these are event-conditioned effects
measured gross under a maker regime; H04's strategy failure stands.
Graduation: H51 pre-registers the fade STRATEGIES (the only intraday
effects in 112 trials that clear the toll with margin).
