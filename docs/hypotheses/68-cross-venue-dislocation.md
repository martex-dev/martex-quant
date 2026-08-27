# Hypothesis 68 — Cross-Venue Price Dislocation (family F2 kill test)

Status: **PRE-REGISTERED 2026-08-27. NO RESULT EXISTS.** Trials declared:
**+12 → 164.** Verdict will be written into §8 and nowhere else.

First hypothesis in family **F2 (cross-exchange basis and price
dislocation)** of `docs/research/family-expansion-program.md`, the family
that document ranks as having the **highest structural independence** of
anything untested. Per CLAUDE.md this is a **kill test**, not a strategy
build.

**Committed before any study code exists.** The data was collected first
(`scripts/pull_venues.py`, 2026-08-27), which runs no study and decides
nothing. Same order as H65 and H67.

**Not to be confused with H10.** `docs/hypotheses/10-spot-perp-basis.md`
tested spot-vs-perp basis on a *single* venue (Binance) and failed
backwards. This tests the *same instrument on different venues*, which
`docs/research/graveyard-audit.md` §5 lists as untested entirely.

---

## 1. Claim

The same asset trades at different prices on different venues, and the
size of that difference — measured in the same currency on both sides —
carries information about forward returns.

## 2. Why the edge should exist

`OBSERVATION` — venue prices differ because the flows behind them differ.
A regulated USD venue (Coinbase) is reached by US institutions and US
retail through fiat rails; a USDT venue (Binance, OKX) is reached by
offshore flow through stablecoin rails. The two are joined only by
arbitrageurs who must hold inventory on both sides and move fiat between
them, which is slow, capital-expensive, and periodically blocked outright
by banking friction. A persistent gap is what an incompletely arbitraged
market looks like.

`OBSERVATION` — the "Coinbase premium" is a widely watched retail folk
signal, which is a reason for suspicion, not for confidence. This project
has killed folk signals repeatedly (H08 funding extremes, H10 basis, H35
pairs reversion).

`OBSERVATION` — **the direction the ledger points.** Meta-finding 1, with
five-plus independent confirmations: crypto is a **continuation** market.
Every crowding or strength signal predicted continuation and every
contrarian reading of one died. So the pre-registered prediction here is
the continuation one — a high premium means US buyers are lifting offers
and that persists — and §5 records it as such **before** the run.

`OBSERVATION` — the counter-prior, stated plainly: **the arbitrage
version of this family is dead at retail and is not what is being
tested.** Cross-venue arbitrage is among the most competed strategies in
crypto; it needs co-located latency and pre-funded inventory on every
venue. Daily closes cannot see it and we could not execute it. What this
test asks is narrower and honest: does the dislocation that *survives to
the daily close* predict anything?

## 3. When it should fail

- **If the gap is mechanically the stablecoin, not the asset.** A
  BTC/USDT price and a BTC/USD price are quoted in different currencies.
  If USDT trades at $0.99 the USDT price is ~1% higher for the same
  economic value. §4.3 decomposes this rather than assuming it away, and
  S1-vs-S2 is the test of whether the folk signal is just tether.
- **If it is momentum in disguise.** If the venue that leads a rally
  simply prints first, the premium is a one-day return transform and any
  signal is already inside the deployed book. §5.4 makes this a mandatory
  diagnostic.
- **If daily closes are too coarse.** Real dislocations may open and shut
  intraday, leaving only noise at 00:00 UTC.
- **If it is real but too small.** Meta-finding 7's pattern: four intraday
  reversion premia measured 2-4bp/event, all real, all below cost. §5.3
  sets the reachability rule in advance.

## 4. Specification

### 4.1 Venues, and what each choice costs

| Venue | Role | Status |
|---|---|---|
| **Coinbase Exchange** (USD) | the fiat/US leg | **included** |
| **Binance** (USDT) | offshore leg, and the venue the deployed book trades | **included** |
| **OKX** (USDT) | second offshore leg, for dispersion | **included** |
| **Bitfinex** USDT/USD | the peg series | **included** (reaches 2018-11-27; Coinbase, OKX and Bitstamp return nothing for this pair) |
| Bitstamp (USD) | second fiat leg | **EXCLUDED** — collected, then dropped. Median daily volume on alts runs $2k-$600k (SKL $2k, BNB $34k, NEAR $54k, AAVE $142k). At those volumes a daily "close" is a stale last trade, not a price, and it would inject microstructure noise exactly where this hypothesis is most fragile. Data retained on disk; the exclusion is recorded, not hidden. |
| Bybit (USDT) | third offshore leg | **EXCLUDED** — spot history starts 2021-07-05; including it costs ~30% of the window for a third venue of a type we already have two of. |
| Kraken | fiat leg | **EXCLUDED** — its OHLC endpoint returns only the ~720 most recent candles regardless of `since`, so it cannot supply history at all. |

All four collected venues stamp daily bars at **00:00 UTC**, so closes
are synchronous without resampling.

`OBSERVATION` — data-quality bridge to the rest of the ledger: a fresh
Binance BTC/USDT pull is **byte-identical** to the frozen research lake
on all **2,747** overlapping days (verified 2026-08-27). This study uses
the venue dataset for both signal and forward returns rather than mixing
stores, and that check is what makes it comparable to trials that use the
lake.

### 4.2 Panel

The 20 universe bases quoted on **all three** study venues that clear a
**$1,000,000/day median quote-volume floor on every venue leg**. The
floor is fixed in advance, computed over each symbol's full common
history, and **no alternative floor is tested**.

Qualifying: AAVE, ADA, ARB, BNB, BTC, DOGE, ENA, ETH, HBAR, LINK, LTC,
NEAR, PEPE, SOL, SUI, UNI, WLD, XLM, XRP, ZEC. **31,752 symbol-days**,
2019-01-01 → 2026-08-27.

Excluded by the floor: SKL ($0.20M), XPL ($0.54M), VIRTUAL ($0.28M),
TAO ($0.96M).

### 4.3 The four signals, and the decomposition

For symbol *s* on day *t*, with all prices as natural logs:
`c` = Coinbase USD close, `b` = Binance USDT close, `o` = OKX USDT close,
`g` = Bitfinex USDT/USD close.

A USDT-quoted price converts to USD by multiplying by the peg, so a
USDT venue's log-USD price is `b + g`.

| # | Signal | Definition | What it isolates |
|---|---|---|---|
| **S1** | raw premium | `c − b` | the naive "Coinbase premium", peg NOT removed |
| **S2** | peg-adjusted premium | `c − (b + g)` | the asset dislocation alone |
| **S3** | dispersion | `stdev{c, b+g, o+g}` | how much the three venues disagree in USD |
| **S4** | peg deviation | `g` | the stablecoin, alone |

**`S1 = S2 + S4` exactly.** That identity is the point: if S1 signals and
S2 does not, the folk signal was tether all along, and the ledger will
say so.

All four are reported in basis points.

### 4.4 Protocol — identical machinery to H08 and H10

- Signal state: **trailing 90-day percentile rank** per symbol.
  **LOW ≤ 10th** percentile, **HIGH ≥ 90th**. Window and thresholds
  **FIXED**; no alternatives tested.
- Forward returns: **Binance** close-to-close log returns — the venue the
  deployed book actually trades — at **h ∈ {1, 7, 30}** days.
- Statistic: pooled `E[fwd | HIGH] − E[fwd | LOW]`, 95% **block bootstrap,
  30-day blocks**, 5,000 resamples, **seed 20260827**.
- **Primary horizon: 7 days**, matching H08 and H10 so this trial is
  comparable to them.

### 4.5 The declared cells — 12 trials, no more

**4 signals × 3 horizons = 12 cells. All twelve reported regardless of
outcome**, including the unflattering ones. No venue pair other than
Coinbase-vs-Binance is tested for S1/S2: venue shopping across four
venues would be six pairs and a guaranteed false positive.

## 5. Pre-registered bars

### 5.1 What counts as a SIGNAL

A cell is a **SIGNAL** only if **both** hold at the primary horizon:

1. the 95% block-bootstrap CI on the pooled `HIGH − LOW` difference
   **excludes zero**, and
2. **breadth ≥ 12 of 20 symbols** share the sign of the pooled estimate.
   (H08/H10 required 5/8 = 62.5%; 12/20 = 60% is the nearest equivalent
   on this panel.)

**NOISE** = CI includes zero. **REVERSED** = CI excludes zero on the side
opposite the §5.2 prediction; per H10's precedent that is recorded as
FAILED-as-registered and is worth nothing until separately pre-registered.

### 5.2 Direction predictions, fixed before the run

- **S1, S2 — predicted POSITIVE.** High premium → higher forward returns.
  This is the continuation reading, and it is what meta-finding 1's five
  confirmations point to. A contrarian result here would be the first
  crowding signal in this ledger to work backwards from continuation.
- **S4 — predicted POSITIVE.** Peg at or above $1 means no offshore
  stress; peg below means risk-off. Continuation again.
- **S3 — no directional prior is declared.** Dispersion is a magnitude,
  not a direction, and inventing a prior to look rigorous would be worse
  than admitting there isn't one. Judged on the CI; the sign is reported.

### 5.3 Reachability rule, declared now so it cannot be negotiated later

A cell reaching SIGNAL proceeds to a strategy hypothesis **only if the
HIGH−LOW spread at h=7 exceeds 0.5%**. Round-trip cost on the project's
standard model is ~0.22% (10bp fee + 1bp half-spread, both sides), so
0.5% is roughly 2× margin. Below that, meta-finding 7's pattern applies —
real, and not ours — and F2 closes without a build.

### 5.4 Mandatory diagnostic: is it just momentum?

Report the correlation of each signal with **trailing 1-day and 7-day
Binance returns**, and the pooled forward-return difference **after
removing symbol-day observations in the top and bottom trailing-return
deciles**. This is the confound most likely to manufacture a false
positive here: if the premium is a return transform, a "signal" is
already inside the deployed momentum book and the incremental bar, not
the info bar, is the one that matters.

**Reported, explicitly NOT gated:** symbol count by year, per-symbol sign
table, the S1 = S2 + S4 decomposition in bp, mean and percentile spread
of each signal, and behaviour of S4 around known depeg events.

## 6. Disposition, declared in advance

- **A cell is a SIGNAL and clears §5.3** → register a follow-on strategy
  hypothesis. It will face the incremental bar against the deployed book,
  not zero. **This test deploys nothing and makes nothing paper-eligible.**
- **SIGNAL but below §5.3's 0.5%** → recorded as a measured premium out of
  reach, alongside the intraday reversion family. **F2 closes, no build.**
- **S1 signals and S2 does not** → the finding is that the Coinbase
  premium is the **tether peg**, not an asset dislocation. That is a real
  result about a widely used retail signal and gets said plainly.
- **All twelve cells NOISE** → **KILLED.** The honest reading would be
  that whatever cross-venue dislocation exists does not survive to the
  daily close in a form that predicts anything.

## 7. Known limitations, stated before results

- **Daily closes only, and therefore the arbitrage question is not
  answered.** A dislocation that opens and closes inside a day is
  invisible here. This study can only see what persists to 00:00 UTC.
  Nothing in this document should later be cited as evidence about
  cross-venue arbitrage, which needs order-book data this project does
  not have and execution latency it does not have either.
- **Ragged panel.** 2019 is a 2-symbol book and 2026 a 20-symbol book, so
  a pooled statistic weights recent years far more heavily. Symbol count
  by year is a required report.
- **XRP carries a real 904-day hole** — Coinbase suspended XRP/USD from
  2021-01-19 over the SEC suit and relisted in 2023. The inner join drops
  those days. This is a true trading halt, not a collection defect; the
  collector was fixed to step over it after it truncated the series once.
- **Survivorship, and it bites in the wrong direction.** The panel is
  today's universe. A venue delisting a collapsing asset removes it from
  the panel *exactly when its premium would have been most extreme*, so
  the most informative observations are the ones most likely to be absent.
- **One venue's peg.** S2 and S4 inherit Bitfinex's own USDT/USD basis.
  A different peg source would shift both by a small, unmeasured amount.
- **The volume floor is a median**, so a qualifying symbol can still be
  below $1M on individual days, particularly early in its listing.
- **Residual collection artifacts.** OKX serves many pairs only from
  2020-01-01, and a few Coinbase series begin on a January boundary
  (PEPE 2025-01-01, AAVE 2021-01-01) rather than a true listing date.
  Months, not years, and they shorten the sample rather than biasing the
  signal.
- **No costs are charged.** This is an info-grade study of forward
  returns. §5.3 is the only place cost enters, and only as a rule about
  what may proceed.

---

## 8. VERDICT

*(Not yet run. This section is written only when the study executes.)*
