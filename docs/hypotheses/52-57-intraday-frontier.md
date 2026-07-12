# Hypotheses 52-57 — Intraday Frontier Batch

Status: **4 of 6 RUN (2026-07-13): H52, H55, H56 KILLED; H57 signal
but sub-toll (closed). H53/H54 pending data fetch.** Ledger: +6 -> 120.
Verdicts at the bottom.

Motivation: the intraday price-SHAPE canon is now fully tested and
dead (H44-51). What remains are (a) the one near-validated lead —
the first-hour fade under true maker fills (51b proxy: Sharpe 0.90,
corr +0.01 to rotation-stop, the most independent stream ever
measured here) — and (b) INFORMATION dimensions never used: aggressor
imbalance, positioning (OI), and intraday cross-coin structure.
Profitable day traders' surviving edges, if any, live in better costs
and better information — both are exactly what this batch tests.

## H52 — First-hour fade, TRUE maker-fill model (+1 trial)

51b re-tested with the fill rule the H51 doc specified but did not
run: entry is a LIMIT at the 00:45 signal close, valid ONE bar only —
filled iff the 01:00 bar's range crosses the limit price; missed =
no trade that day. Maker fee 2bp entry, taker exit at day close.
Engine-purity note: the core engine lacks limit orders, so this runs
in a dedicated bar-replay whose fill rule is STRICTER than a real
resting order (one-bar window); if it passes, the engine gains limit
support before any deployment (source-of-truth rule preserved).
Bars: net Sharpe > 0.7 AND corr vs rotation-stop < 0.30. Fill rate
reported (a pass with <30% fills is flagged fragile).

## H53 — Aggressor imbalance (taker-buy ratio) (+1 trial, two-sided)

NEW DATA: Binance USDM 15m klines carry taker-buy volume. imb =
taker_buy/volume - 0.5, smoothed 4 bars. Extreme imbalance (|z|>2 vs
trailing 1d) -> next 1h signed return in the imbalance direction.
Continuation claim from the microstructure literature; two-sided.

## H54 — Open-interest divergence (+1 trial, two-sided)

NEW DATA: Bybit OI history (1h, as far back as the API serves).
4h price move split by concurrent 4h OI change: price-up+OI-up (new
longs) vs price-up+OI-down (short covering) -> fwd 4h difference.
Two-sided; the squeeze-exhaustion claim says covering-driven rallies
fade.

## H55 — BTC -> alt intraday lead-lag (+1 trial, two-sided)

Existing 15m panel: BTC 15m return |z|>2 (vs trailing 1d) -> alts'
NEXT-15m and next-1h signed follow-through (pooled, alt panel).
H19 found a daily down-day echo; this is the minutes version the
arb desks supposedly closed. The data referees.

## H56 — Intraday ETH/BTC ratio reversion (+1 trial, two-sided)

Meta-finding: intraday reverts. Applied market-neutrally: log ETH/BTC
ratio z vs trailing 1d; |z|>2 -> next 2h signed reversion. Daily
ratio momentum near-missed (H35); intraday is the opposite regime.

## H57 — Prior-day volume-profile POC reaction (+1 trial, two-sided)

Retail "market profile" canon, testable core: prior day's POC = the
volume-weighted modal price (15m closes binned into 20 buckets,
volume-weighted). On the first bar that touches the POC after opening
away from it: next-1h signed move toward vs away (magnet vs bounce
recorded by sign). Two-sided.

## Shared protocol

15m/1h panels; day-block bootstrap (30d, 5,000 draws), 95% CI;
features use data <= t; gross effects with the maker toll (~0.04% RT)
printed. Verdict = CI excludes 0 (direction recorded). Strategy-grade
graduation only via a further pre-registered spec; nothing joins the
live book mid-sprint.

## Verdicts (2026-07-13, scripts/h52_55_57_studies.py)

- **H52: KILLED — Sharpe 0.69 vs the 0.70 bar** (corr +0.015, fill
  rate 100%, CAGR +19.0%, MDD -45.6%). The honest fill model explains
  the proxy's flattery: after an up first hour, price often continues
  into 01:00, so the proxy's market entry shorted HIGHER than a
  resting limit at the signal close. Near-miss stays closed. (A
  resting-until-filled fill window would be a new spec — deliberately
  NOT run now; iterating fill models until one passes is forking-paths
  hacking. If ever reopened it needs its own registration and a raised
  bar.)
- H55 lead-lag: next-15m +0.010% (CI includes 0), next-1h -0.002% —
  KILLED. The minutes-scale echo is fully arbitraged.
- H56 ratio reversion: -0.017% CI [-0.037, +0.0002] — KILLED; the
  near-miss is AGAIN on the momentum side (even intraday, the ratio
  wants to trend, echoing H35).
- **H57 POC: SIGNAL, sub-toll — closed.** +0.028% per event, CI
  [+0.0002, +0.056]: statistically real, economically dead (< 4bp
  maker RT). Recorded as the cleanest example yet of a true retail
  observation that cannot pay its own execution.
- H53 (aggressor imbalance) and H54 (OI divergence): data fetch in
  progress; verdicts pending.
