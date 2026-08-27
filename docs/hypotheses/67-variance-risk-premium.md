# Hypothesis 67 — Variance Risk Premium (family F3 kill test)

Status: **PRE-REGISTERED 2026-08-27. NO RESULT EXISTS.** Trials declared:
**+5 → 152.** Verdict will be written into §8 and nowhere else.

First hypothesis in family **F3 (options / variance risk premium)** of
`docs/research/family-expansion-program.md`. Per CLAUDE.md this is a
**kill test**, not a strategy build: it decides whether the expensive part
of F3 — a Deribit option-chain collector, a Greeks layer, and an
event-driven straddle spec — is worth building at all.

**Committed before any study code exists.** The data was collected first
(`scripts/pull_dvol.py`, 2026-08-27), which runs no study and decides
nothing. Same order as H65.

---

## 1. Claim

Implied volatility on BTC and ETH exceeds the volatility that
subsequently realizes, by a margin large enough to survive the real cost
of harvesting it at retail on Deribit.

## 2. Why the edge should exist

`OBSERVATION` — the variance risk premium is the most robustly documented
premium in any market. In equity index options it has been measured
positive over essentially every multi-year window since listed options
existed. The economic story is not a behavioural quirk: option sellers
carry a short position in a risk that is (a) negatively correlated with
wealth and (b) has unbounded loss, so they demand compensation. Buyers
pay it because insurance against a crash is worth more than its
actuarial cost to someone who is already long.

`OBSERVATION` — crypto's version of this should be **larger**, because
crypto's crash risk is larger and the natural sellers of that insurance
(institutional vol desks) entered late and remain small relative to the
demand.

`OBSERVATION` — the counter-prior, recorded honestly: **this project has
now confirmed four separate times that a premium being real does not
make it reachable.** The intraday reversion premium was measured at
2–4bp/event across four confirmations and died on a 10bp taker fee. VRP
is harvested through options, which are the *most* cost-laden instrument
retail can touch. §5 Gate B exists specifically because of this prior.

`OBSERVATION` — the correlation prior, and it points the wrong way. Carry
(H62) cleared the correlation bar at +0.0041 because funding is
mechanically unrelated to price direction. **Short volatility is not
mechanically unrelated to price direction** — it loses in crashes, and so
does a long-momentum book. F3 may pay well and still fail the objective
of `family-expansion-program.md` §2, which is *uncorrelated* edges, not
merely profitable ones. Gate C is therefore not a formality here.

## 3. When it should fail

- **If crypto IV is fairly priced.** Unlike equities, crypto's realized
  vol has repeatedly exceeded 100%; sellers may simply have been right to
  charge what they charge.
- **If the premium is smaller than the cost of reaching it.** The §4
  haircut is 3.0 vol points. If the gross premium is 2 vol points, the
  family is dead for retail regardless of how real it is.
- **If the premium is a few episodes.** Short vol earns a little most of
  the time and loses enormously rarely. A positive mean over 1,900 days
  that is really "no crash big enough happened in-sample" is not an edge,
  it is an unpaid insurance claim. §7 records that the single worst
  episode in crypto's history (March 2020) is **outside** our window.
- **If it is just short-beta.** Gate C.

## 4. Specification

### 4.1 Data

- **Implied:** Deribit **DVOL**, the venue's model-free 30-day
  forward-looking volatility index, daily close,
  `data/dvol/{BTC,ETH}.parquet`, 1,983 bars each, 2021-03-24 →
  2026-08-27. Free, no auth.
- **Realized:** daily closes from the **frozen research baseline**
  `data/lake` (ends 2026-07-09) — the same store H62–H66 used. Not
  `data/lake-current`, so this trial stays comparable to the rest of the
  ledger.
- **Effective study window:** 2021-03-25 → 2026-07-09, bounded by the lake.

### 4.2 The proxy instrument

We cannot price options without a chain, and collecting the chain is the
expensive step this test is meant to gate. So the harvest is modelled as
a **rolling ladder of 30-day short variance positions**, delta-hedged,
which is the standard analytic stand-in for a delta-hedged short straddle:

- Every day `t`, open a tranche of notional `1/30` of capital, struck at
  `K_t` = DVOL close of day `t` (decimal, e.g. 0.60).
- Each tranche lives exactly 30 days. Thirty tranches are live at all
  times. Total underlying notional = **1x capital** (the same 1x
  convention as H62, and for the same reason: no leverage claim is being
  made).
- A tranche accrues variance P&L daily. Summed over a tranche's life this
  is exactly `K_t^2 - RV_t^2`.

**Daily return of the book, per unit of capital:**

```
ret_u = V * ( Kbar2_u - 365*r_u^2 ) / ( 2*Kbar_u * 30 )  -  V * h / 30
```

- `r_u` = log return of the spot close on day `u`.
- `Kbar2_u` = mean of `K_t^2` over the 30 live tranches, `t` in
  `[u-30, u-1]`; `Kbar_u` is its square root. **Every strike is strictly
  earlier than the return it is paid against; there is no lookahead by
  construction.**
- `V = 2*phi(0)*sqrt(30/365) = 0.228734` — the vega of a 30-day ATM
  straddle per unit of underlying notional per 1.00 of decimal vol. This
  is what converts vol points into percent-of-notional.
- `h` = the cost haircut in decimal vol, derived in §4.3.

### 4.3 The cost haircut, derived in advance

`h` is **derived, not fitted**, and every input is stated so the
derivation can be attacked rather than trusted. At 30 days ATM:

| Component | Derivation | Vol points |
|---|---|---|
| Deribit option fees | 0.03%·S per contract x 2 legs to open + 0.015%·S x 2 at settlement = 0.09%·S. Premium cap (12.5% of premium, about 1.7%·S) is not binding. `0.0009 / 0.228734` | **0.393** |
| Option half-spread | Deribit 30d ATM quotes run about 1–2 vol points wide; charge 0.5 per leg, entry only (held to expiry) | **1.000** |
| Delta-hedge slippage | Daily rehedge on the perp. Expected daily turnover `= 2*phi(0)*E|z| / (sqrt(T)*sqrt(365)) = 0.1162*S`, **independent of the vol level** (gamma falls as sigma rises, exactly offsetting the larger moves). Over 30 days = 3.487·S at the project's standard 11bp (10bp fee + 1bp half-spread) = 0.3836%·S. `0.003836 / 0.228734` | **1.677** |
| | **total** | **3.070** |

**Base haircut `h = 0.03` (3.0 vol points).** All three components are
**invariant to the level of implied vol** (ATM vega does not depend on
sigma, and hedge turnover is sigma-invariant as shown), so a flat haircut
is the right functional form here, not a convenience.

In return terms the haircut costs `V*h/30 = 2.287 bp/day = 8.35%/yr`.
That is the hurdle the gross premium must clear before anything else.

### 4.4 The declared cells — 5 trials, no more

| # | Cell | Purpose |
|---|---|---|
| 1 | BTC alone, `h`=0.03, overlapping ladder | per-asset |
| 2 | ETH alone, `h`=0.03, overlapping ladder | per-asset |
| **3** | **Combined 50/50 BTC+ETH — PRIMARY** | the book the bars judge |
| 4 | Combined, **non-overlapping** (one tranche, opened every 30 days) | sample honesty |
| 5 | Combined, **2x haircut** (`h`=0.06) | cost sensitivity |

**All five are reported regardless of outcome.** No horizon grid exists
to search: DVOL is a 30-day index, so the tenor is fixed by the data, not
chosen. No conditioning variant is tested here — "sell vol only when IV
is rich" is the obvious refinement and it is deliberately **excluded**,
to be registered as its own hypothesis only if this test passes. Baking
it in would turn a kill test into a search.

## 5. Pre-registered bars

**Gate A — is there a premium, after costs?** (judged on cell 3)

1. Mean daily net > 0 with a 95% **block-bootstrap CI excluding zero**,
   **60-day blocks** (double the 30-day tranche life, because overlapping
   tranches and volatility clustering both induce autocorrelation).
2. Net CAGR ≥ **2%/yr**.
3. Sharpe ≥ **1.0**.
4. `DSR_global` ≥ **0.95** at **N = 152**.

**Gate B — is it worth building the options stack?**

5. **Cell 5 (2x haircut) still has mean net > 0 with CI excluding zero.**
   The haircut is derived, not measured (§7). If doubling our own cost
   estimate kills the result, then the estimate is producing the edge and
   we have not measured the market.
6. **Cell 4 (non-overlapping) has CAGR > 0 and Sharpe ≥ 1.0.** The
   premium must not be an artifact of counting the same 30 days 30 times.

**Gate C — is it independent?**

7. **|correlation| with rotation-stop < 0.30**, timestamp-joined on the
   daily stream, per meta-finding 5 (join on timestamp, never position).

**Reported, explicitly NOT gated:** MDD, worst 30- and 90-day windows,
per-year table, skew and excess kurtosis, behaviour in the named stress
episodes (May-2021, LUNA, FTX, and every 2024–2026 drawdown), and the
gap between the variance form used here and the simple `K - RV` form.

**Tail condition, declared now so it cannot be negotiated later:** if the
proxy MDD is worse than **−40%**, then any F3 build must design its tail
limits (notional caps, wing protection) **before** the build, not after.
This is a condition on how we would proceed, not a bar that can fail.

## 6. Disposition, declared in advance

- **A + B + C** → **PROCEED to the F3 build.** Register a follow-on
  hypothesis for a Deribit option-chain collector, Greeks, and an
  event-driven short-straddle spec. **This test deploys nothing and makes
  nothing paper-eligible** — the proxy is not the instrument.
- **A + C, not B** → premium real, our reach unproven. **Closed, no
  build.** Recorded as a measured premium in the same category as the
  intraday reversion finding: real, and not ours at these costs.
- **A + B, not C** → the premium is short-beta in disguise. Recorded, and
  **de-prioritized** against the eight-uncorrelated-edges objective even
  though it pays. F3 would then be competing with the deployed book, not
  adding to it.
- **A fails** → **KILLED.** The honest reading would be that crypto's
  implied vol was fairly priced over 2021–2026 at the 30-day tenor on the
  only two assets that publish an index.

## 7. Known limitations, stated before results

- **The worst episode is outside the sample.** DVOL begins 2021-03-24.
  March 2020 — the largest short-vol loss in crypto's history — is not in
  this window and cannot be. **Every number this study produces is
  therefore biased in the hypothesis's favour**, by an amount we cannot
  quantify. This is the most important line in this document.
- **The family can never be broad.** Only BTC and ETH have usable DVOL
  history (SOL has a 408-point 2022 stub; XRP and MATIC have none). The
  two series are highly correlated, so the effective independent sample
  is far below the nominal 2 x 1,900. Breadth is not available as a
  remedy here, unlike F1.
- **The proxy is not the instrument.** The accrual formula is *exact* for
  a variance swap and *approximate* for the delta-hedged short straddle a
  retail account would actually sell. The linearization drops the term
  that hurts most in large moves, so real straddle P&L is **worse** than
  modelled in exactly the scenarios that matter.
- **The haircut is derived, not measured.** No Deribit order-book history
  was collected; the 1.0 vol-point option half-spread is an estimate.
  Gate B5 exists because of this, and a pass here is trustworthy only up
  to 2x our own cost guess.
- **Margin and liquidation are ignored**, exactly as H62 §7 ignored them.
  A short straddle can be liquidated intraday on a move that a daily-bar
  study never sees. 1x notional makes this less severe, not absent.
- **Continuous 30-day tenor is an idealization.** Real Deribit options
  expire weekly/monthly; a real ladder rolls into listed expiries with
  tenor drift and non-ATM strikes.
- **No conditioning, no parameter search.** Deliberate — see §4.4.
- **Delta hedging is assumed perfect.** Hedge error (the difference
  between daily rehedging and continuous) is charged as slippage but not
  as tracking error, which adds variance the study does not show.

---

## 8. VERDICT

*(Not yet run. This section is written only when the study executes.)*
