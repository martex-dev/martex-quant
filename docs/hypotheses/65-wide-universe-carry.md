# Hypothesis 65 — Wide-Universe Carry (family F1 expansion)

Status: **PRE-REGISTERED 2026-08-27, NOT RUN.** Trials: **+3 → 144.**

Extends `docs/hypotheses/63-funding-conditional-carry.md` (Sharpe 6.00,
CAGR +4.51%, MDD −0.51% on **8** majors) to the full perp universe.

**Committed before any study code exists.** No result exists at the time of
writing. The data was collected first (`scripts/pull_carry_universe.py`,
27 symbols added, existing 8 caches untouched and verified by checksum).

---

## 1. Claim

Carry is a **cross-sectional** premium, not a property of eight large
coins. Running the H63 specification across **every** symbol with a
Binance USDM perp should raise the Sharpe of the carry book, because more
symbols means more independent funding streams and the idiosyncratic part
of each diversifies away.

## 2. Why the edge should exist — and the prior in its favour

`OBSERVATION` — **meta-finding 3** of this project: *"Cross-sectional edges
feed on breadth. Rotation got STRONGER on 40 coins than 8 (Sharpe 0.90 →
1.10) — opposite of the survivorship fear."*

That is a directly relevant precedent, and unlike H63's prior it points
**toward** this hypothesis. Funding on a small alt is paid by the same
crowded-long mechanism as funding on BTC, and small alts are typically
*more* crowded, so both the premium and its dispersion should be larger.

`OBSERVATION` — the counter-prior, recorded honestly: smaller symbols have
**wider spreads and thinner books** than the cost model assumes. The
project charges a flat 10bp fee + 1bp half-spread everywhere. That is
roughly right for BTC and roughly **optimistic** for a coin listed in 2025.
See §7.

## 3. When it should fail

- **If the premium is a large-cap phenomenon.** Small-alt funding may be
  noise around zero rather than a persistent positive.
- **If costs eat the breadth gain.** More symbols means more rebalancing
  turnover on exactly the coins where the flat cost model is least honest.
- **If short history dominates.** Many new symbols carry two years or less;
  a book weighted equally across them is mostly recent history.

## 4. Specification

**Identical to H63 in every respect** — 1× collateralization, always-on
subject to the trailing-funding filter, daily rebalance, the project's cost
model on both legs, funding accrued on real 8-hour settlement stamps —
with exactly two changes:

1. **Universe:** every symbol in `config/universe.json` that has all three
   of spot (lake), perp, and funding. Fixed by data availability, not by
   choice, and enumerated in the verdict.
2. **Panel mode:** union rather than intersection
   (`require_all_symbols=False`). A symbol participates on the days it
   exists; capital is split equally across whatever is available that day.
   Intersecting 35 ragged histories would collapse the window to the
   newest listing and is not a meaningful test.

**Grid:** the same declared `L ∈ {7, 30, 90}` as H63, primary **L = 30**.
Re-running the grid on a different universe is the robustness check that
matters here — a plateau on 8 symbols that vanishes on 35 would mean the
H63 result was universe-specific. **All three cells reported. 3 trials.**

## 5. Pre-registered bars

**Gate A — is the wide book an edge at all?**

1. Mean daily net > 0, 95% block-bootstrap CI (30-day blocks) excluding zero.
2. Net CAGR ≥ 2%/yr after all costs.
3. Sharpe ≥ 1.0.
4. `DSR_global` ≥ 0.95 at N = 144.

**Gate B — does breadth actually help?**

5. **Sharpe > the 8-symbol incumbent's**, and
6. **CAGR > the 8-symbol incumbent's**,

both measured **on the identical window, with the incumbent recomputed in
the same run.**

> The incumbent's figures **will differ from H63's published 2.29 / +4.51%**
> because the comparison window differs — the 8-symbol book is re-run in
> union mode over the shared date range. That is deliberate. Importing
> H63's published numbers and comparing them to a different window is
> exactly the FU-B1 defect recorded in
> `docs/research/graveyard-audit.md` §2.1, and it will not be repeated.

**Gate C — is it still independent?**

7. **|correlation| with rotation-stop < 0.30**, timestamp-joined. Breadth
   must not smuggle in directional exposure.

## 6. Disposition, declared in advance

- **A + B + C** → replaces H63 as the carry spec; paper-eligible.
- **A + C, not B** → **STANDALONE-VIABLE**. Real, but breadth did not
  help; H63's 8-symbol spec remains the carry spec. This would be a
  genuine negative result about meta-finding 3's scope: breadth helps
  cross-sectional *momentum* but not carry.
- **A fails** → **KILLED**, and the honest reading is that the carry
  premium measured on 8 majors does not generalize.

## 7. Known limitations, stated before results

- **The cost model is most optimistic exactly where this hypothesis adds
  symbols.** 10bp + 1bp is defensible for BTC; for a thin 2025 listing the
  true half-spread is likely multiples of 1bp. **Any Gate B pass driven by
  small alts is therefore an upper bound, not an estimate.** If Gate B
  passes, the honest follow-up is a cost-sensitivity study, not deployment.
- **Survivorship.** The universe is the top 40 by volume as of 2026-07-12.
  Perps that were delisted are absent, and delisting correlates with the
  kind of collapse that would hurt a short-perp book.
- **Ragged history.** Symbols enter as they list. Early years are an
  8-coin book and recent years a 35-coin book, so a Sharpe improvement may
  partly reflect *when* the extra symbols existed rather than *that* they
  existed. The verdict must report the symbol count over time.
- **1× only**, and the intraday-liquidation limitation from H62 §7 is
  inherited unchanged.
- Five universe symbols have no USDM perp (ATMUSDT, PEPEUSDT, PYRUSDT,
  SPCXBUSDT, UUSDT) and are structurally excluded.
