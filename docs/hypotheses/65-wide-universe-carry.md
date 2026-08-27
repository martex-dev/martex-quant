# Hypothesis 65 — Wide-Universe Carry (family F1 expansion)

Status: **STANDALONE-VIABLE (2026-08-27) — real edge, breadth did NOT
help.** Trials: **+3 → 144.** Verdict in §8. Wide book Sharpe 5.60 vs the
8-symbol incumbent's 5.91 on the same window: Gate A and C pass, Gate B
fails. NOT deployed; H63 remains the carry spec. First use of
docs/research/standalone-viable-amendment.md.

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

---

## 8. VERDICT (2026-08-27, scripts/h65_wide_carry_study.py, +3 → 144)

**STANDALONE-VIABLE.** Gate A passes, Gate C passes, **Gate B fails**.
Breadth did **not** help. H63's 8-symbol spec remains the carry spec.

Wide universe: **34 symbols** with spot + perp + funding. Shared comparison
window 2019-09-11 → 2026-07-09, both books run in union mode.

| | 8 majors (incumbent) | **34 symbols (wide)** |
|---|---|---|
| Sharpe | **5.91** | 5.60 |
| CAGR | **+4.64%** | +4.36% |
| MDD | −0.84% | −0.76% |

### The declared grid — all three cells

| L | Sharpe | CAGR | MDD | DSR | mean bp/day |
|---|---|---|---|---|---|
| 7 | 4.23 | +4.15% | −2.62% | 1.0000 | +1.113 |
| **30 (primary)** | **5.60** | **+4.36%** | **−0.76%** | **1.0000** | **+1.170** |
| 90 | 5.71 | +3.95% | −0.53% | 1.0000 | +1.060 |

| Gate | Bar | Measured | Result |
|---|---|---|---|
| A1 | CI excludes zero | +0.669 bp low | **PASS** |
| A2 | CAGR ≥ 2%/yr | +4.36% | **PASS** |
| A3 | Sharpe ≥ 1.0 | 5.60 | **PASS** |
| A4 | DSR ≥ 0.95 @144 | 1.0000 | **PASS** |
| B5 | Sharpe > 5.91 | 5.60 | **FAIL** |
| B6 | CAGR > +4.64% | +4.36% | **FAIL** |
| C7 | \|corr\| rot-stop < 0.30 | **−0.0040** | **PASS** |

### 8.1 The finding: meta-finding 3 does not extend to carry

`OBSERVATION` — the prior recorded in §2 pointed *toward* this hypothesis:
meta-finding 3 says *"cross-sectional edges feed on breadth — rotation got
STRONGER on 40 coins than 8 (Sharpe 0.90 → 1.10)."* Carry does the
opposite. Going from 8 to 34 symbols **lowered** Sharpe 5.91 → 5.60 and
CAGR +4.64% → +4.36%.

`INTERPRETATION` — breadth helps a **selection** edge and not a **harvest**
edge, and the mechanism is plausible: rotation picks the best few of many,
so more candidates is strictly more to choose from. Carry holds everything
that pays, so more symbols adds more *average* funding, not more *selected*
funding — and the marginal symbol is a thinner, later listing whose
funding is closer to zero. Diluting 8 rich streams with 26 thin ones is
not diversification, it is dilution.

**Proposed refinement to meta-finding 3, for PROJECT_MEMORY:** *breadth
feeds cross-sectional edges that SELECT; it dilutes edges that HARVEST.*
Stated as a hypothesis for future testing, not as an established rule —
this is one measurement in one family.

> **REFUTED 2026-08-27 by H66**, which was registered to test exactly this
> and predicted top-K would beat harvest-all. It does not, monotonically:
> K=3 → 2.27, K=5 → 2.99, K=10 → 4.06, harvest-all → 5.60. The refinement
> above must NOT be quoted as a project finding. H66 §8.3 gives the better
> explanation — carry's Sharpe is a diversification property, not a
> premium-size one — and notes that this also undercuts the dilution story
> in §8.1. **This verdict's own bars and figures are unchanged;** only the
> speculative refinement is withdrawn.

### 8.2 Why this is STANDALONE-VIABLE and not KILLED

`OBSERVATION` — the wide book clears **every** absolute bar: mean
+1.170 bp/day with a CI excluding zero, CAGR +4.36%, Sharpe 5.60, DSR
1.0000 at 144 trials, and correlation −0.0040 with the deployed momentum
book.

`INTERPRETATION` — under the rule as it stood before 2026-08-27 this would
have been recorded **KILLED**, in the same bucket as H04 mean-reversion,
which had no edge at all. It plainly has an edge; it simply has a slightly
worse one than the incumbent. This is the first use of
`docs/research/standalone-viable-amendment.md` and it is the case the
amendment was written for.

**It is not deployed**, and per the amendment it does **not** count toward
the eight-edge target: it is the same edge as H63, harvested more widely,
not an independent one.

### 8.3 The ragged-history caveat, quantified as §7 required

| Year | avg symbols | net %/yr |
|---|---|---|
| 2019 | 1.3 | +1.49 |
| 2020 | 11.1 | +6.17 |
| **2021** | 16.8 | **+16.72** |
| 2022 | 17.0 | −0.14 |
| 2023 | 19.8 | +1.96 |
| 2024 | 23.9 | +4.48 |
| **2025** | 30.0 | **−0.08** |
| **2026** | 33.7 | **−0.78** |

`OBSERVATION` — the symbol count rises monotonically while returns fall.
The years with the most symbols are the worst years.

`INTERPRETATION` — this confounds the breadth test and the honest reading
is that it **cannot be fully separated** from it: the extra symbols exist
mostly in 2024-2026, which is also when funding went thin. Gate B's
failure is therefore *consistent with* dilution but not proven to be
dilution rather than timing. §8.1's proposed refinement is offered with
that caveat attached, and a clean test would need a universe held constant
through time.

`OBSERVATION` — the dead recent regime is unchanged and unfixed by
breadth: **2025 −0.08%/yr, 2026 −0.78%/yr.** Third independent
confirmation, after H62 and H63, that carry earns approximately nothing
today.

### 8.4 The §7 cost caveat did not need to be invoked

`OBSERVATION` — §7 warned that a Gate B pass driven by small alts would be
an upper bound requiring a cost-sensitivity study before deployment.

`INTERPRETATION` — Gate B **failed under the optimistic cost model**.
Charging honest wider spreads on thin listings would only widen the gap, so
the follow-up study is unnecessary: the conclusion cannot flip in the
direction that would matter.
